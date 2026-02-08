"""
Credit Note API Views
Handle credit notes for sales returns and adjustments.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from datetime import date

from apps.orders.models import CreditNote, CreditNoteLine
from apps.invoice.models import Invoice
from apps.party.models import Party


class CreditNoteListCreateView(APIView):
    """
    List all credit notes or create a new one.
    
    GET /api/orders/credit-notes/
    POST /api/orders/credit-notes/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List credit notes with filters"""
        company = request.company
        
        credit_notes = CreditNote.objects.filter(
            company=company
        ).select_related('party', 'reference_invoice', 'created_by')
        
        # Filter by status
        cn_status = request.query_params.get('status')
        if cn_status:
            credit_notes = credit_notes.filter(status=cn_status.upper())
        
        # Filter by party
        party_id = request.query_params.get('party')
        if party_id:
            credit_notes = credit_notes.filter(party_id=party_id)
        
        data = []
        for cn in credit_notes:
            data.append({
                "id": str(cn.id),
                "credit_note_number": cn.credit_note_number,
                "credit_note_date": cn.credit_note_date.isoformat(),
                "party_id": str(cn.party.id),
                "party_name": cn.party.name,
                "reference_invoice_number": cn.reference_invoice.invoice_number if cn.reference_invoice else None,
                "reference_type": cn.reference_type,
                "reason": cn.reason,
                "status": cn.status,
                "total_amount": str(cn.total_amount),
                "created_at": cn.created_at.isoformat()
            })
        
        return Response(data, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def post(self, request):
        """Create a new credit note"""
        company = request.company
        user = request.user
        
        # Validate required fields
        party_id = request.data.get('party_id')
        if not party_id:
            return Response(
                {"error": "party_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            party = Party.objects.get(id=party_id, company=company)
        except Party.DoesNotExist:
            return Response(
                {"error": "Party not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get reference invoice if provided
        reference_invoice = None
        invoice_id = request.data.get('reference_invoice_id')
        if invoice_id:
            try:
                reference_invoice = Invoice.objects.get(id=invoice_id, company=company)
            except Invoice.DoesNotExist:
                return Response(
                    {"error": "Invoice not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Generate credit note number
        from apps.company.models import Sequence
        seq, created = Sequence.objects.get_or_create(
            company=company,
            key='credit_note',
            defaults={'prefix': 'CN-', 'last_value': 0}
        )
        seq.last_value += 1
        seq.save()
        cn_number = f"{seq.prefix}{str(seq.last_value).zfill(6)}"
        
        # Create credit note
        credit_note = CreditNote.objects.create(
            company=company,
            credit_note_number=cn_number,
            credit_note_date=request.data.get('credit_note_date', date.today()),
            party=party,
            reference_invoice=reference_invoice,
            reference_type=request.data.get('reference_type', 'INVOICE'),
            reason=request.data.get('reason', ''),
            status=request.data.get('status', 'DRAFT'),
            created_by=user
        )
        
        # Add line items
        lines_data = request.data.get('lines', [])
        subtotal = 0
        tax_amount = 0
        
        for idx, line in enumerate(lines_data, start=1):
            line_taxable = float(line.get('taxable_value', 0))
            cgst_amt = float(line.get('cgst_amount', 0))
            sgst_amt = float(line.get('sgst_amount', 0))
            igst_amt = float(line.get('igst_amount', 0))
            line_total = line_taxable + cgst_amt + sgst_amt + igst_amt
            
            CreditNoteLine.objects.create(
                credit_note=credit_note,
                line_no=idx,
                product_id=line.get('product_id'),
                description=line.get('description', ''),
                quantity=line.get('quantity', 0),
                unit_rate=line.get('unit_rate', 0),
                taxable_value=line_taxable,
                cgst_rate=line.get('cgst_rate', 0),
                cgst_amount=cgst_amt,
                sgst_rate=line.get('sgst_rate', 0),
                sgst_amount=sgst_amt,
                igst_rate=line.get('igst_rate', 0),
                igst_amount=igst_amt,
                line_total=line_total
            )
            
            subtotal += line_taxable
            tax_amount += (cgst_amt + sgst_amt + igst_amt)
        
        # Update totals
        credit_note.subtotal = subtotal
        credit_note.tax_amount = tax_amount
        credit_note.total_amount = subtotal + tax_amount
        credit_note.save()
        
        return Response({
            "message": "Credit note created successfully",
            "id": str(credit_note.id),
            "credit_note_number": credit_note.credit_note_number
        }, status=status.HTTP_201_CREATED)


class CreditNoteDetailView(APIView):
    """
    Get, update, or delete a credit note.
    
    GET /api/orders/credit-notes/<id>/
    PATCH /api/orders/credit-notes/<id>/
    DELETE /api/orders/credit-notes/<id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, cn_id):
        """Get credit note details"""
        company = request.company
        
        try:
            cn = CreditNote.objects.select_related(
                'party', 'reference_invoice', 'created_by'
            ).get(id=cn_id, company=company)
        except CreditNote.DoesNotExist:
            return Response(
                {"error": "Credit note not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get lines
        lines = CreditNoteLine.objects.filter(credit_note=cn).select_related('product')
        
        line_items = []
        for line in lines:
            line_items.append({
                "id": str(line.id),
                "line_no": line.line_no,
                "product_id": str(line.product.id) if line.product else None,
                "product_name": line.product.name if line.product else None,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_rate": str(line.unit_rate),
                "taxable_value": str(line.taxable_value),
                "cgst_rate": str(line.cgst_rate),
                "cgst_amount": str(line.cgst_amount),
                "sgst_rate": str(line.sgst_rate),
                "sgst_amount": str(line.sgst_amount),
                "igst_rate": str(line.igst_rate),
                "igst_amount": str(line.igst_amount),
                "line_total": str(line.line_total)
            })
        
        data = {
            "id": str(cn.id),
            "credit_note_number": cn.credit_note_number,
            "credit_note_date": cn.credit_note_date.isoformat(),
            "party": {
                "id": str(cn.party.id),
                "name": cn.party.name
            },
            "reference_invoice": {
                "id": str(cn.reference_invoice.id),
                "invoice_number": cn.reference_invoice.invoice_number
            } if cn.reference_invoice else None,
            "reference_type": cn.reference_type,
            "reason": cn.reason,
            "status": cn.status,
            "subtotal": str(cn.subtotal),
            "tax_amount": str(cn.tax_amount),
            "total_amount": str(cn.total_amount),
            "notes": cn.notes,
            "lines": line_items,
            "created_by": cn.created_by.username,
            "created_at": cn.created_at.isoformat()
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def patch(self, request, cn_id):
        """Update credit note (only for DRAFT status)"""
        company = request.company
        
        try:
            cn = CreditNote.objects.get(id=cn_id, company=company)
        except CreditNote.DoesNotExist:
            return Response(
                {"error": "Credit note not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if cn.status != 'DRAFT':
            return Response(
                {"error": "Can only update draft credit notes"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update status if provided
        if 'status' in request.data:
            cn.status = request.data['status']
            cn.save()
        
        return Response({
            "message": "Credit note updated successfully",
            "status": cn.status
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, cn_id):
        """Delete credit note (only DRAFT)"""
        company = request.company
        
        try:
            cn = CreditNote.objects.get(id=cn_id, company=company)
        except CreditNote.DoesNotExist:
            return Response(
                {"error": "Credit note not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if cn.status != 'DRAFT':
            return Response(
                {"error": "Can only delete draft credit notes"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cn.delete()
        return Response(
            {"message": "Credit note deleted successfully"},
            status=status.HTTP_200_OK
        )
