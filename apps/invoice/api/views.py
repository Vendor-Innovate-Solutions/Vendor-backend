"""
Invoice API views.
RESTful endpoints for invoice management, generation, and posting.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError

from core.permissions.base import RolePermission
from apps.orders.models import SalesOrder
from apps.invoice.models import Invoice
from apps.invoice.api.serializers import (
    InvoiceSerializer, InvoiceListSerializer, CreateInvoiceFromOrderSerializer
)
from apps.invoice.selectors import list_outstanding_invoices, get_invoice
from apps.invoice.services.invoice_generation_service import InvoiceGenerationService
from core.services.posting import PostingService


# ================================================================
# 1) Create invoice from sales order
# ================================================================
class InvoiceFromSalesOrderView(APIView):
    """
    Generate an invoice from a confirmed sales order.
    
    POST: Create invoice from sales order
    Requires: ADMIN, ACCOUNTANT, or SALES_MANAGER role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT', 'SALES_MANAGER'])]
    
    def post(self, request, so_id):
        """Generate invoice from sales order."""
        company = request.company
        serializer = CreateInvoiceFromOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get sales order
            sales_order = SalesOrder.objects.get(company=company, id=so_id)
            
            # Check order status
            if sales_order.status not in ['CONFIRMED', 'IN_PROGRESS']:
                return Response(
                    {'error': f'Cannot create invoice from {sales_order.status} order'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate invoice
            invoice = InvoiceGenerationService.generate_from_sales_order(
                sales_order=sales_order,
                created_by=request.user,
                partial_allowed=serializer.validated_data.get('partial_allowed', False),
                apply_gst=serializer.validated_data.get('apply_gst', True),
                company_state_code=serializer.validated_data.get('company_state_code') or getattr(company, 'state_code', '')
            )
            
            response_serializer = InvoiceSerializer(invoice)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to generate invoice: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# 2) Post invoice → triggers stock posting + GL posting
# ================================================================
class InvoicePostingView(APIView):
    """
    Post an invoice to the accounting system.
    
    POST: Post invoice (creates voucher, updates stock, updates ledgers)
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request, invoice_id):
        """Post invoice to accounting system."""
        company = request.company
        
        try:
            # Get invoice
            invoice = Invoice.objects.get(company=company, id=invoice_id)
            
            # Check invoice status
            if invoice.status == 'POSTED':
                return Response(
                    {'error': 'Invoice already posted', 'voucher_id': str(invoice.voucher.id) if invoice.voucher else None},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if invoice.status == 'CANCELLED':
                return Response(
                    {'error': 'Cannot post cancelled invoice'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Post invoice using posting service
            posting_service = PostingService()
            
            # Create voucher from invoice if not exists
            if not invoice.voucher:
                voucher = posting_service.create_voucher_from_invoice(invoice)
                invoice.voucher = voucher
                invoice.save(update_fields=['voucher'])
            
            # Post the voucher
            posted_voucher = posting_service.post_voucher(
                voucher_id=invoice.voucher.id,
                posted_by=request.user
            )
            
            # Update invoice status
            invoice.status = 'POSTED'
            invoice.save(update_fields=['status'])
            
            return Response({
                'voucher_id': str(posted_voucher.id),
                'voucher_number': posted_voucher.voucher_number,
                'status': 'POSTED',
                'message': 'Invoice posted successfully'
            })
            
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to post invoice: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# 3) Outstanding invoices
# ================================================================
class InvoiceOutstandingView(APIView):
    """
    List all outstanding (unpaid/partially paid) invoices.
    
    GET: List outstanding invoices
    """
    
    def get(self, request):
        """List outstanding invoices for the company."""
        company = request.company
        
        # Get outstanding invoices
        qs = list_outstanding_invoices(company)
        
        # Apply additional filters
        invoice_type = request.query_params.get('invoice_type')
        if invoice_type:
            qs = qs.filter(invoice_type=invoice_type)
        
        party_id = request.query_params.get('party')
        if party_id:
            qs = qs.filter(party_id=party_id)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        
        serializer = InvoiceListSerializer(qs, many=True)
        return Response(serializer.data)


# ================================================================
# 4) List/Get invoice details
# ================================================================
class InvoiceListView(APIView):
    """
    List all invoices for the company.
    
    GET: List invoices with filters
    """
    
    def get(self, request):
        """List invoices with optional filters."""
        company = request.company
        
        # Get all invoices
        qs = Invoice.objects.filter(company=company).select_related(
            'party', 'currency', 'sales_order', 'purchase_order'
        ).order_by('-invoice_date', '-created_at')
        
        # Apply filters
        invoice_status = request.query_params.get('status')
        if invoice_status:
            qs = qs.filter(status=invoice_status)
        
        invoice_type = request.query_params.get('invoice_type')
        if invoice_type:
            qs = qs.filter(invoice_type=invoice_type)
        
        party_id = request.query_params.get('party')
        if party_id:
            qs = qs.filter(party_id=party_id)
        
        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        
        serializer = InvoiceListSerializer(qs, many=True)
        return Response(serializer.data)


class InvoiceDetailView(APIView):
    """
    Get invoice details with line items.
    
    GET: Get invoice details
    """
    
    def get(self, request, invoice_id):
        """Get invoice details."""
        company = request.company
        
        try:
            invoice = get_invoice(company, invoice_id)
            serializer = InvoiceSerializer(invoice)
            return Response(serializer.data)
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InvoiceDownloadView(APIView):
    """
    Download invoice as PDF.
    
    GET: Download invoice PDF
    """
    
    def get(self, request, invoice_id):
        """Generate and download invoice PDF."""
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from io import BytesIO
        
        company = request.company
        
        try:
            invoice = get_invoice(company, invoice_id)
            
            # Create PDF buffer
            buffer = BytesIO()
            
            # Create PDF document
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            
            # Container for PDF elements
            elements = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a202c'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            # Company header
            elements.append(Paragraph(f"<b>{company.name}</b>", title_style))
            if company.address:
                elements.append(Paragraph(f"{company.address}", styles['Normal']))
            if hasattr(company, 'gstin') and company.gstin:
                elements.append(Paragraph(f"GSTIN: {company.gstin}", styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Invoice title
            invoice_title = ParagraphStyle('InvoiceTitle', parent=styles['Heading2'], alignment=TA_CENTER)
            elements.append(Paragraph(f"<b>INVOICE: {invoice.invoice_number}</b>", invoice_title))
            elements.append(Spacer(1, 0.2*inch))
            
            # Invoice details table
            details_data = [
                ['Invoice Date:', invoice.invoice_date.strftime('%d-%m-%Y'), 'Due Date:', (invoice.due_date or invoice.invoice_date).strftime('%d-%m-%Y')],
                ['Party:', invoice.party.name if invoice.party else 'N/A', 'Status:', invoice.status],
            ]
            details_table = Table(details_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
            details_table.setStyle(TableStyle([
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#374151')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(details_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Line items table
            line_items_data = [['#', 'Product', 'Quantity', 'Rate', 'Tax', 'Amount']]
            
            for idx, line in enumerate(invoice.lines.all(), 1):
                line_items_data.append([
                    str(idx),
                    line.product.name if line.product else line.description or 'N/A',
                    f"{line.quantity:.2f}",
                    f"₹{line.rate:.2f}",
                    f"₹{line.tax_amount:.2f}",
                    f"₹{line.amount:.2f}"
                ])
            
            # Add totals
            line_items_data.append(['', '', '', '', 'Subtotal:', f"₹{invoice.taxable_value:.2f}"])
            if invoice.cgst_amount > 0:
                line_items_data.append(['', '', '', '', 'CGST:', f"₹{invoice.cgst_amount:.2f}"])
            if invoice.sgst_amount > 0:
                line_items_data.append(['', '', '', '', 'SGST:', f"₹{invoice.sgst_amount:.2f}"])
            if invoice.igst_amount > 0:
                line_items_data.append(['', '', '', '', 'IGST:', f"₹{invoice.igst_amount:.2f}"])
            line_items_data.append(['', '', '', '', 'Total:', f"₹{invoice.invoice_amount:.2f}"])
            
            line_items_table = Table(line_items_data, colWidths=[0.4*inch, 2.5*inch, 1*inch, 1*inch, 1*inch, 1.2*inch])
            line_items_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 11),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                # Data rows
                ('FONTNAME', (0,1), (-1,-6), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                # Grid
                ('GRID', (0,0), (-1,-6), 1, colors.HexColor('#d1d5db')),
                ('LINEBELOW', (0,-5), (-1,-1), 0.5, colors.HexColor('#d1d5db')),
                # Totals section
                ('FONTNAME', (4,-5), (-1,-1), 'Helvetica-Bold'),
                ('BACKGROUND', (4,-1), (-1,-1), colors.HexColor('#f3f4f6')),
                ('TOPPADDING', (0,1), (-1,-1), 6),
                ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ]))
            elements.append(line_items_table)
            
            # Build PDF
            doc.build(elements)
            
            # Get PDF value
            pdf = buffer.getvalue()
            buffer.close()
            
            # Return PDF response
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
            response.write(pdf)
            return response
            
        except Invoice.DoesNotExist:
            return Response(
                {'error': 'Invoice not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to generate PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
