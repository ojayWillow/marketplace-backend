"""Email service for sending transactional emails using Resend."""

import os
import requests


class EmailService:
    """
    Email service for sending transactional emails.
    Uses Resend API for reliable email delivery.
    """
    
    def __init__(self):
        self.resend_api_key = os.getenv('RESEND_API_KEY', '')
        self.from_email = os.getenv('FROM_EMAIL', 'onboarding@resend.dev')
        self.from_name = os.getenv('FROM_NAME', 'Marketplace')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        self.resend_api_url = 'https://api.resend.com/emails'
    
    def send_email(self, to_email, subject, html_content, text_content=None, debug_info=None):
        """
        Send an email using Resend API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Plain text fallback (optional)
            debug_info: Extra info to print in dev mode (optional)
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            # Check if Resend is configured
            if not self.resend_api_key:
                print(f"\n{'='*60}")
                print(f"[EMAIL] Resend API not configured - DEV MODE")
                print(f"{'='*60}")
                print(f"To: {to_email}")
                print(f"Subject: {subject}")
                if debug_info:
                    print(f"\n{debug_info}")
                print(f"{'='*60}\n")
                return True  # Return True in dev mode so the flow continues
            
            print(f"[EMAIL] Sending email via Resend to {to_email}")
            
            # Prepare the request
            headers = {
                'Authorization': f'Bearer {self.resend_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'from': f'{self.from_name} <{self.from_email}>',
                'to': [to_email],
                'subject': subject,
                'html': html_content
            }
            
            if text_content:
                payload['text'] = text_content
            
            # Send via Resend API
            response = requests.post(
                self.resend_api_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"[EMAIL] Successfully sent email to {to_email}, ID: {result.get('id')}")
                return True
            else:
                print(f"[EMAIL] Resend API error: {response.status_code} - {response.text}")
                return False
            
        except requests.exceptions.Timeout:
            print(f"[EMAIL] Resend API request timed out")
            return False
        except Exception as e:
            print(f"[EMAIL] Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, to_email, username, reset_token):
        """
        Send password reset email with reset link.
        
        Args:
            to_email: User's email address
            username: User's username for personalization
            reset_token: The password reset token
        
        Returns:
            bool: True if sent successfully
        """
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset Your Password - Marketplace"
        
        # Debug info for dev mode
        debug_info = f"PASSWORD RESET LINK:\n{reset_link}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #3B82F6, #2563EB); padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">Password Reset</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">
                <p style="font-size: 16px;">Hi <strong>{username}</strong>,</p>
                
                <p style="font-size: 16px;">We received a request to reset your password. Click the button below to create a new password:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background: #3B82F6; color: white; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block;">Reset Password</a>
                </div>
                
                <p style="font-size: 14px; color: #6b7280;">This link will expire in <strong>1 hour</strong> for security reasons.</p>
                
                <p style="font-size: 14px; color: #6b7280;">If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.</p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 25px 0;">
                
                <p style="font-size: 12px; color: #9ca3af;">If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="font-size: 12px; color: #3B82F6; word-break: break-all;">{reset_link}</p>
            </div>
            
            <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
                <p>&copy; 2026 Marketplace. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {username},
        
        We received a request to reset your password.
        
        Click this link to reset your password:
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request this, you can safely ignore this email.
        
        - Marketplace Team
        """
        
        return self.send_email(to_email, subject, html_content, text_content, debug_info)


# Singleton instance
email_service = EmailService()
