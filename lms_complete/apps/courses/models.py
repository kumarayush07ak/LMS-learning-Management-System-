from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.contrib.auth import get_user_model
import os
from django.core.validators import MinValueValidator, MaxValueValidator


User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Course(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=200, blank=True)
    
    instructor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='courses_taught',
        limit_choices_to={'user_type': 'instructor'}
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='courses'
    )
    
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False)
    
    total_enrollments = models.PositiveIntegerField(default=0)
    average_rating = models.FloatField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            original_slug = self.slug
            queryset = Course.objects.filter(slug=self.slug)
            count = 1
            while queryset.exists():
                self.slug = f"{original_slug}-{count}"
                count += 1
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('courses:courses_detail', kwargs={'slug': self.slug})


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    content = models.TextField(help_text="HTML content for the lesson")
    video_url = models.URLField(blank=True, help_text="YouTube URL")
    
    order = models.PositiveIntegerField(default=0)
    is_free_preview = models.BooleanField(default=False)
    duration_minutes = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    

class LessonFile(models.Model):
    """Model for lesson files (PDFs, documents, etc.)"""
    FILE_TYPES = [
        ('pdf', 'PDF Document'),
        ('doc', 'Word Document'),
        ('ppt', 'PowerPoint'),  
        ('zip', 'Archive'),
        ('other', 'Other'),
    ]
    
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='files')
    title = models.CharField(max_length=200)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='pdf')
    file = models.FileField(upload_to='lesson_files/')
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    description = models.TextField(blank=True)
    
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def filename(self):
        return os.path.basename(self.file.name)
    
    def size_display(self):
        """Return human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class LessonFolder(models.Model):
    """Model for organizing lesson files into folders"""
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.lesson.title} - {self.name}"


class FolderFile(models.Model):
    """Files inside folders"""
    folder = models.ForeignKey(LessonFolder, on_delete=models.CASCADE, related_name='files')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='folder_files/')
    file_size = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

class CourseReview(models.Model):
    """Reviews for courses by students"""
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='reviews')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_reviews')  # This is fine
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)

    would_recommend = models.BooleanField(default=True)
    difficulty_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Difficulty rating from 1 (Easy) to 5 (Very Hard)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False, help_text="Student has completed the course")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['course', 'student']  
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.course.title} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_course_rating()
    
    def update_course_rating(self):
        """Update the course's average rating"""
        from django.db.models import Avg
        avg = self.course.reviews.aggregate(Avg('rating'))['rating__avg']
        self.course.average_rating = round(avg, 2) if avg else 0
        self.course.total_reviews = self.course.reviews.count()
        self.course.save()


class InstructorReview(models.Model):
    """Reviews for instructors by students"""
    instructor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews_received',  
        limit_choices_to={'user_type': 'instructor'}
    )
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews_given',  
    )
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='instructor_reviews')
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    comment = models.TextField(blank=True)
    
    # Teaching quality metrics
    clarity_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Clarity of instruction"
    )
    responsiveness_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
        help_text="Responsiveness to questions"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['instructor', 'student', 'course']  
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.instructor.get_full_name()} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        self.update_instructor_rating()
    
    def update_instructor_rating(self):
        """Update the instructor's average rating"""
        from django.db.models import Avg
        avg = InstructorReview.objects.filter(instructor=self.instructor).aggregate(Avg('rating'))['rating__avg']
        
        
        if hasattr(self.instructor, 'instructor_rating'):
            self.instructor.instructor_rating = round(avg, 2) if avg else 0
            self.instructor.total_instructor_reviews = InstructorReview.objects.filter(instructor=self.instructor).count()
            self.instructor.save()


class ReviewHelpful(models.Model):
    """Track which users found a review helpful"""
    review = models.ForeignKey(CourseReview, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['review', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name()} found {self.review} helpful"