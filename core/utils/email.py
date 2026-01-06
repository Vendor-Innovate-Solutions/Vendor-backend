"""
Email notification utilities.
"""
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_otp_email(user, otp):
    """
    Send OTP via email for password reset
    """
    subject = 'Password Reset OTP - Vendor Management System'
    
    # Create HTML email content
    html_message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">Password Reset Request</h2>
            <p>Hello {user.first_name or user.username},</p>
            <p>You have requested to reset your password for your Vendor Management System account.</p>
            
            <div style="background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin: 0; color: #333;">Your OTP Code:</h3>
                <p style="font-size: 24px; font-weight: bold; color: #007bff; margin: 10px 0; letter-spacing: 3px;">{otp}</p>
            </div>
            
            <p><strong>Important:</strong></p>
            <ul>
                <li>This OTP is valid for 10 minutes only</li>
                <li>Do not share this OTP with anyone</li>
                <li>If you didn't request this, please ignore this email</li>
            </ul>
            
            <p>Best regards,<br>Vendor Management System Team</p>
        </div>
    </body>
    </html>
    """
    
    # Create plain text version
    plain_message = f"""
    Password Reset Request
    
    Hello {user.first_name or user.username},
    
    You have requested to reset your password for your Vendor Management System account.
    
    Your OTP Code: {otp}
    
    Important:
    - This OTP is valid for 10 minutes only
    - Do not share this OTP with anyone
    - If you didn't request this, please ignore this email
    
    Best regards,
    Vendor Management System Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"OTP email sent successfully to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
        return False


def send_password_reset_confirmation(user):
    """
    Send confirmation email after successful password reset
    """
    subject = 'Password Reset Successful - Vendor Management System'
    
    html_message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #28a745;">Password Reset Successful</h2>
            <p>Hello {user.first_name or user.username},</p>
            <p>Your password has been successfully reset for your Vendor Management System account.</p>
            
            <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
                <p style="margin: 0; color: #155724;">✓ Your password has been updated successfully</p>
            </div>
            
            <p>If you did not make this change, please contact our support team immediately.</p>
            
            <p>Best regards,<br>Vendor Management System Team</p>
        </div>
    </body>
    </html>
    """
    
    plain_message = f"""
    Password Reset Successful
    
    Hello {user.first_name or user.username},
    
    Your password has been successfully reset for your Vendor Management System account.
    
    If you did not make this change, please contact our support team immediately.
    
    Best regards,
    Vendor Management System Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Password reset confirmation email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email to {user.email}: {str(e)}")
        return False


def send_company_invite_email(invite, base_url="https://vendor-frontend-production-be99.up.railway.app"):
    """
    Send company invitation email to retailer
    """
    subject = f'Invitation to join {invite.company.name} - Vendor Management System'
    
    # Create invite link
    invite_link = f"{base_url}/join-company?code={invite.invite_code}"
    
    # Create HTML email content
    html_message = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">You're Invited to Join {invite.company.name}</h2>
            <p>Hello,</p>
            <p>{invite.invited_by.first_name or invite.invited_by.username} from <strong>{invite.company.name}</strong> has invited you to join their vendor network.</p>
            
            {f'<p><em>"{invite.message}"</em></p>' if invite.message else ''}
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin: 0; color: #333;">Join using this link:</h3>
                <p style="margin: 10px 0;">
                    <a href="{invite_link}" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Join {invite.company.name}
                    </a>
                </p>
                <p style="margin: 10px 0; font-size: 14px; color: #666;">
                    Or use invite code: <strong style="background-color: #e9ecef; padding: 4px 8px; border-radius: 3px;">{invite.invite_code}</strong>
                </p>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0;"><strong>Note:</strong></p>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    <li>This invitation expires on {invite.expires_at.strftime('%B %d, %Y at %I:%M %p')}</li>
                    <li>You'll need to create an account if you don't have one</li>
                    <li>This invitation can only be used once</li>
                </ul>
            </div>
            
            <h3>About {invite.company.name}</h3>
            <p>{invite.company.description or 'A trusted vendor partner in our network.'}</p>
            <p><strong>Location:</strong> {invite.company.city}, {invite.company.state}</p>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
            <p style="color: #666; font-size: 12px;">
                If you didn't expect this invitation, you can safely ignore this email.
                <br>This invitation was sent by {invite.invited_by.email} from {invite.company.name}.
            </p>
        </div>
    </body>
    </html>
    """
    
    # Create plain text version
    plain_message = f"""
    You're Invited to Join {invite.company.name}
    
    Hello,
    
    {invite.invited_by.first_name or invite.invited_by.username} from {invite.company.name} has invited you to join their vendor network.
    
    {f'Message: "{invite.message}"' if invite.message else ''}
    
    Join using this link: {invite_link}
    Or use invite code: {invite.invite_code}
    
    About {invite.company.name}:
    {invite.company.description or 'A trusted vendor partner in our network.'}
    Location: {invite.company.city}, {invite.company.state}
    
    This invitation expires on {invite.expires_at.strftime('%B %d, %Y at %I:%M %p')}
    
    Best regards,
    Vendor Management System Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Company invite email sent successfully to {invite.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send company invite email to {invite.email}: {str(e)}")
        return False


def send_request_status_email(retailer_request, approved=True):
    """
    Send email notification when retailer request is approved/rejected
    """
    status_text = "Approved" if approved else "Rejected"
    subject = f'Your request to join {retailer_request.company.name} has been {status_text}'
    
    if approved:
        html_message = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">Request Approved! 🎉</h2>
                <p>Great news! Your request to join <strong>{retailer_request.company.name}</strong> has been approved.</p>
                
                <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
                    <p style="margin: 0;"><strong>You can now:</strong></p>
                    <ul style="margin: 5px 0; padding-left: 20px;">
                        <li>Browse their product catalog</li>
                        <li>Place orders</li>
                        <li>Access company resources</li>
                        <li>Communicate directly with the team</li>
                    </ul>
                </div>
                
                <p>Login to your account to start exploring the partnership opportunities.</p>
                
                <p>Welcome to the {retailer_request.company.name} vendor network!</p>
            </div>
        </body>
        </html>
        """
        
        plain_message = f"""
        Request Approved!
        
        Great news! Your request to join {retailer_request.company.name} has been approved.
        
        You can now:
        - Browse their product catalog
        - Place orders
        - Access company resources
        - Communicate directly with the team
        
        Login to your account to start exploring the partnership opportunities.
        
        Welcome to the {retailer_request.company.name} vendor network!
        """
    else:
        html_message = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">Request Status Update</h2>
                <p>Thank you for your interest in joining <strong>{retailer_request.company.name}</strong>.</p>
                
                <p>After careful consideration, we are unable to approve your request to join our vendor network at this time.</p>
                
                <p>This decision may be due to:</p>
                <ul>
                    <li>Current capacity limitations</li>
                    <li>Geographic restrictions</li>
                    <li>Specific business requirements</li>
                </ul>
                
                <p>You're welcome to apply again in the future or contact us directly for more information.</p>
                
                <p>Thank you for your understanding.</p>
            </div>
        </body>
        </html>
        """
        
        plain_message = f"""
        Request Status Update
        
        Thank you for your interest in joining {retailer_request.company.name}.
        
        After careful consideration, we are unable to approve your request to join our vendor network at this time.
        
        This decision may be due to:
        - Current capacity limitations
        - Geographic restrictions  
        - Specific business requirements
        
        You're welcome to apply again in the future or contact us directly for more information.
        
        Thank you for your understanding.
        """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[retailer_request.retailer.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Request status email sent to {retailer_request.retailer.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send status email to {retailer_request.retailer.email}: {str(e)}")
        return False
