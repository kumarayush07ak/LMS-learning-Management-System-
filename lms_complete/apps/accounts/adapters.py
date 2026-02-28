from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect
from allauth.exceptions import ImmediateHttpResponse
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter - ONLY ALLOWS LOGIN FOR EXISTING USERS
    """
    
    def is_open_for_signup(self, request, sociallogin):
        """Disable social signup completely"""
        return False
    
    def pre_social_login(self, request, sociallogin):
        """
        Check if email exists in database before allowing login
        """
        # Get email from Google
        email = sociallogin.account.extra_data.get('email')
        
        if not email:
            messages.error(request, 'Could not get email from Google account.')
            raise ImmediateHttpResponse(redirect('accounts:login'))
        
        try:
            # Try to find existing user by email
            user = User.objects.get(email=email)
            
            # User exists - connect social account if not already connected
            if not sociallogin.is_existing:
                sociallogin.connect(request, user)
                logger.info(f"Connected Google account to existing user: {email}")
            
        except User.DoesNotExist:
            # User doesn't exist - prevent login
            logger.info(f"Attempted Google login for non-existent email: {email}")
            messages.error(
                request, 
                'No account found with this email. Please register first using the signup form.'
            )
            raise ImmediateHttpResponse(redirect('accounts:register'))