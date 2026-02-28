from django.db import models
from django.contrib.auth import get_user_model
from apps.courses.models import Course
from django.utils import timezone

User = get_user_model()


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    progress = models.PositiveIntegerField(default=0)
    
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    last_accessed = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-enrolled_at']
    
    def __str__(self):
        return f"{self.student.email} - {self.course.title}"
    
    def save(self, *args, **kwargs):
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Update course enrollment count
        self.update_course_enrollment_count()
    
    def delete(self, *args, **kwargs):
        course = self.course
        super().delete(*args, **kwargs)
        
        self.update_course_enrollment_count(course)
    
    def update_course_enrollment_count(self, course=None):
        """Update the total_enrollments field in the associated course"""
        if course is None:
            course = self.course
        
        # Count active enrollments for this course
        count = Enrollment.objects.filter(course=course).count()
        course.total_enrollments = count
        course.save()
    
    def update_progress(self):
        total_lessons = self.course.lessons.count()
        if total_lessons == 0:
            self.progress = 0
        else:
            self.progress = min(self.progress + 10, 100)
        
        if self.progress >= 100 and self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
        
        self.save()