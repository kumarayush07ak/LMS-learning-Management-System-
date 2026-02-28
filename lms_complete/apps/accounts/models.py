from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import random
import string
from django.utils import timezone
from datetime import timedelta


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    USER_TYPES = (
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('admin', 'Administrator'),
    )
    
    username = None
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='student')
    
    # Profile fields
    phone_number = models.CharField(max_length=15, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Email verification fields
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # Django's default is True
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_student(self):
        return self.user_type == 'student'
    
    @property
    def is_instructor(self):
        return self.user_type == 'instructor'
    
    @property
    def is_admin_user(self):
        return self.user_type == 'admin' or self.is_superuser


class EmailVerificationOTP(models.Model):
    """Store OTP for email verification"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_otp')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Email Verification OTP"
        verbose_name_plural = "Email Verification OTPs"
    
    def __str__(self):
        return f"{self.user.email} - {self.otp}"
    
    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """Check if OTP is expired (10 minutes)"""
        expiry_time = self.created_at + timedelta(minutes=10)
        return timezone.now() > expiry_time
    
    @classmethod
    def create_otp(cls, user):
        """Create or update OTP for user"""
        otp, created = cls.objects.update_or_create(
            user=user,
            defaults={
                'otp': cls.generate_otp(),
                'is_verified': False
            }
        )
        return otp