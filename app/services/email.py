"""Email service for sending transactional emails."""

import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


class EmailService:
    """
    Email service for sending transactional emails.
    
    Supports multiple providers:
    - SMTP (Gmail, Outlook, custom SMTP servers)
    - Can be extended for SendGrid, Mailgun, etc.
    """
    
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.from_name = os.getenv('FROM_NAME', 'Marketplace')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        # Timeout for SMTP operations (in seconds)
        self.smtp_timeout = int(os.getenv('SMTP_TIMEOUT', '10'))
    
    def _create_connection(self):
        """Create SMTP connection with timeout."""
        server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.smtp_timeout)
        server.starttls()
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)
        return server
    
    def send_email(self, to_email, subject, html_content, text_content=None, debug_info=None):
        """
        Send an email.
        
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
            # Check if email is configured
            if not self.smtp_user or not self.smtp_password:
                print(f"\n{'='*60}")
                print(f"[EMAIL] SMTP not configured - DEV MODE")
                print(f"{'='*60}")
                print(f"To: {to_email}")
                print(f"Subject: {subject}")
                if debug_info:
                    print(f"\n{debug_info}")
                print(f"{'='*60}\n")
                return True  # Return True in dev mode so the flow continues
            
            print(f"[EMAIL] Attempting to send email to {to_email}")
            print(f"[EMAIL] SMTP Host: {self.smtp_host}:{self.smtp_port}")
            print(f"[EMAIL] SMTP User: {self.smtp_user}")
            print(f"[EMAIL] Timeout: {self.smtp_timeout}s")
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add plain text version
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            
            # Add HTML version
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email with timeout protection
            print(f"[EMAIL] Connecting to SMTP server...")
            server = self._create_connection()
            print(f"[EMAIL] Connected, sending email...")
            server.sendmail(self.from_email, to_email, msg.as_string())
            server.quit()
            
            print(f"[EMAIL] Successfully sent email to {to_email}")
            return True
            
        except socket.timeout:
            print(f"[EMAIL] SMTP connection timed out after {self.smtp_timeout}s")
            return False
        except smtplib.SMTPAuthenticationError as e:
            print(f"[EMAIL] SMTP Authentication failed: {str(e)}")
            print(f"[EMAIL] Make sure you're using a Gmail App Password, not your regular password")
            print(f"[EMAIL] Get an App Password at: https://myaccount.google.com/apppasswords")
            return False
        except smtplib.SMTPException as e:
            print(f"[EMAIL] SMTP error: {str(e)}")
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
