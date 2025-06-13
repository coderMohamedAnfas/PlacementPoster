import os
from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class CollegeManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:  # Ensure password is not None
            user.set_password(password)  # Properly hashes the password

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class College(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    sheet_url = models.URLField(blank=True, null=True)
    # task_id = models.UUIDField(default="c2869387-f965-4c84-9daf-e1f94193ff68")
    logo = models.ImageField(
        upload_to='college_logos/',
        # default="college_logos/logo.png",
        blank=True,
        null=True,

    )
    current_status = models.TextField(blank=True, null=True)
    pdf = models.FileField(upload_to ='posters/',  blank=True,
        null=True,)    # Required fields for AbstractBaseUser
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Manager
    objects = CollegeManager()

    # Required for AbstractBaseUser
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']  # Fields required for superuser creation

    class Meta:
        verbose_name = "College"
        verbose_name_plural = "Colleges"

    def __str__(self):
        return self.name

class Student(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    prn = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    photo_url = models.URLField(null=True, blank=True)  # URL for the photo if needed
    is_photo = models.BooleanField(default=False)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)
    

    def __str__(self):
        return f"{self.name}-{self.prn}-{self.college.name}"
    
    def delete(self, *args, **kwargs):
        # Check if a photo exists and delete it from storage
        if self.photo:
            if os.path.isfile(self.photo.path):
                os.remove(self.photo.path)
        super().delete(*args, **kwargs)

from django.db import models
from datetime import timedelta

class CommonData(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE,null=True)
    start_year = models.DateField(null=True)  # Admin provides the start year
    end_year = models.DateField(blank=True, null=True)  # Calculated field
    prn_field = models.CharField(max_length=255, blank=True)
    image_field = models.CharField(max_length=255, blank=True)
    name_field = models.CharField(max_length=255,null=True)
    department_field = models.CharField(max_length=255,null=True)

    def save(self, *args, **kwargs):
        if self.start_year:
            self.end_year = self.start_year.replace(year=self.start_year.year + 1)
        super().save(*args, **kwargs)

    
class Company(models.Model):
    name = models.CharField(max_length=50,unique=True,null=True)
    lpa = models.DecimalField(max_digits=5, decimal_places=2)  # Adjust max_digits as needed


class PlacementData(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    # models.py
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True)



# class Poster(models.Model):
#     college = models.ForeignKey(College, on_delete=models.CASCADE)
#     # data = models.JSONField(null=True)  # Store dynamic companies and PRNs
#     created_at = models.DateTimeField(auto_now_add=True)
    
    # def __str__(self):
    #     return f"Poster for {self.college.name}"


