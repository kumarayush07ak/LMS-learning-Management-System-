from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from django.core.mail import send_mail
from django.conf import settings


def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save()

            if user.user_type == 'student':
                subject = "Welcome to Our Portal 🎉"
                message = f"""
Hi {user.get_full_name()},

Welcome to Our Portal!

Thank you for registering as a Student.
We are excited to have you as part of our learning community.

You can now login and start exploring courses.

Best Regards,
Portal Team
"""

            elif user.user_type == 'instructor':
                subject = "Welcome Instructor 🚀"
                message = f"""
Hi {user.get_full_name()},

Welcome to Our Portal!

Congratulations on joining us as an Instructor.
You can now start your journey by creating courses,
sharing knowledge, and inspiring students.

We are excited to have you onboard!

Best Regards,
Portal Team
"""         
            try:
                send_mail(
                    subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [user.email],
                    fail_silently=False,
                )

                messages.success(request, "Registration successful! Welcome email sent.")

            except Exception as e:
                messages.warning(request, f"Registration successful, but email failed: {e}")

            return redirect("accounts:login")

    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})



def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                return redirect('accounts:dashboard')
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