from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, get_backends
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from .models import User, EmailVerificationOTP
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site

def send_otp_email(user, otp):
    """Send OTP verification email using template"""
    subject = 'Verify Your Email - EduFlow'
    
    # Render HTML email from template
    html_message = render_to_string('accounts/email_otp.html', {
        'user': user,
        'otp': otp,
    })
    
    # Create plain text version
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def register_view(request):
    """User registration view with OTP verification"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            user.is_active = True
            user.email_verified = False
            user.save()

            # Create and send OTP
            otp_obj = EmailVerificationOTP.create_otp(user)
            email_sent = send_otp_email(user, otp_obj.otp)

            # Store user ID in session for verification
            request.session['pending_user_id'] = user.id

            if email_sent:
                messages.success(request, 'Registration successful! Please check your email for OTP verification.')
            else:
                messages.warning(request, 'Registration successful but failed to send verification email. Please contact support.')

            return redirect("accounts:verify_otp")
        else:
            # Form errors will be displayed in template
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def verify_otp(request):
    """Verify OTP page"""
    # Check if there's a pending user
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found. Please register again.')
        return redirect('accounts:register')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('accounts:register')
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        
        try:
            otp_obj = EmailVerificationOTP.objects.get(user=user)
            
            if otp_obj.is_verified:
                messages.warning(request, 'Email already verified. Please login.')
                return redirect('accounts:login')
            
            if otp_obj.is_expired():
                messages.error(request, 'OTP has expired. Please request a new one.')
                return redirect('accounts:resend_otp')
            
            if otp_obj.otp == otp_entered:
                otp_obj.is_verified = True
                otp_obj.save()
                user.email_verified = True
                user.save()
                
                # Clear session
                del request.session['pending_user_id']
                
                # FIX: Get the first backend path and use it for login
                backend = get_backends()[0]
                user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
                
                # Log the user in
                login(request, user)
                
                # Send welcome email based on user type
                if user.user_type == 'student':
                    subject = "Welcome to EduFlow! 🎉"
                    message = f"""
Hi {user.get_full_name()},

Welcome to EduFlow!

Thank you for registering as a Student.
We are excited to have you as part of our learning community.

You can now login and start exploring courses.

Best Regards,
EduFlow Team
"""
                elif user.user_type == 'instructor':
                    subject = "Welcome to EduFlow! 🚀"
                    message = f"""
Hi {user.get_full_name()},

Welcome to EduFlow!

Congratulations on joining us as an Instructor.
You can now start your journey by creating courses,
sharing knowledge, and inspiring students.

We are excited to have you onboard!

Best Regards,
EduFlow Team
"""
                else:
                    subject = "Welcome to EduFlow!"
                    message = f"Hi {user.get_full_name()},\n\nWelcome to EduFlow!"

                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=True,
                    )
                except:
                    pass  # Silent fail for welcome email
                
                messages.success(request, 'Email verified successfully! Welcome to EduFlow.')
                return redirect('accounts:dashboard')
            else:
                messages.error(request, 'Invalid OTP. Please try again.')
                
        except EmailVerificationOTP.DoesNotExist:
            messages.error(request, 'OTP not found. Please request a new one.')
            return redirect('accounts:resend_otp')
    
    # Mask email for display
    email_parts = user.email.split('@')
    if len(email_parts[0]) > 3:
        masked_email = email_parts[0][:3] + '***' + '@' + email_parts[1]
    else:
        masked_email = email_parts[0] + '***' + '@' + email_parts[1]
    
    return render(request, 'accounts/verify_otp.html', {
        'email': masked_email,
        'full_email': user.email,
    })


def resend_otp(request):
    """Resend OTP verification email"""
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, 'No pending verification found. Please register again.')
        return redirect('accounts:register')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('accounts:register')
    
    # Create new OTP
    otp_obj = EmailVerificationOTP.create_otp(user)
    email_sent = send_otp_email(user, otp_obj.otp)
    
    if email_sent:
        messages.success(request, 'New OTP has been sent to your email.')
    else:
        messages.error(request, 'Failed to send OTP. Please try again.')
    
    return redirect('accounts:verify_otp')


def login_view(request):
    """User login view with email verification check"""
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            
            if user is not None:
                if not user.email_verified:
                    messages.error(request, 'Please verify your email first. Check your inbox for OTP.')
                    # Create new OTP and redirect to verification
                    otp_obj = EmailVerificationOTP.create_otp(user)
                    send_otp_email(user, otp_obj.otp)
                    request.session['pending_user_id'] = user.id
                    return redirect('accounts:verify_otp')
                
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                return redirect('accounts:dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def dashboard_view(request):
    user = request.user
    
    context = {'user': user}
    
    if user.is_student:
        enrollments = Enrollment.objects.filter(student=user).select_related('course')
        completed_courses = enrollments.filter(status='completed').count()
        in_progress_courses = enrollments.filter(status='in_progress').count()
        
        context.update({
            'enrollments': enrollments[:5],
            'completed_courses': completed_courses,
            'in_progress_courses': in_progress_courses,
            'total_courses': enrollments.count(),
        })
        
    elif user.is_instructor:
        courses = Course.objects.filter(instructor=user)
        total_students = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
        
        context.update({
            'courses': courses[:5],
            'total_courses': courses.count(),
            'total_students': total_students,
        })
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})


def password_reset_request(request):
    """Password reset request page"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate token and uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build reset link
            current_site = get_current_site(request)
            reset_link = f"http://{current_site.domain}/accounts/password-reset/{uid}/{token}/"
            
            # Send email
            subject = "Password Reset Request - EduFlow"
            html_message = render_to_string('accounts/password_reset_email.html', {
                'user': user,
                'protocol': 'http',
                'domain': current_site.domain,
                'uid': uid,
                'token': token,
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('accounts:password_reset_done')
            
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            return redirect('accounts:password_reset')
    
    return render(request, 'accounts/password_reset.html')


def password_reset_done(request):
    """Password reset done page"""
    return render(request, 'accounts/password_reset_done.html')


def password_reset_confirm(request, uidb64, token):
    """Password reset confirm page"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('new_password1')
            password2 = request.POST.get('new_password2')
            
            if password1 != password2:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})
            
            if len(password1) < 8:
                messages.error(request, 'Password must be at least 8 characters.')
                return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})
            
            # Set new password
            user.set_password(password1)
            user.save()
            
            messages.success(request, 'Password has been reset successfully.')
            return redirect('accounts:password_reset_complete')
        
        return render(request, 'accounts/password_reset_confirm.html', {'validlink': True})
    else:
        return render(request, 'accounts/password_reset_confirm.html', {'validlink': False})


def password_reset_complete(request):
    """Password reset complete page"""
    return render(request, 'accounts/password_reset_complete.html')