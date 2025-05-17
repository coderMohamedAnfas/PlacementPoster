from django.contrib import admin

# Register your models here.
from .models import College, Student, Poster,CommonData

admin.site.register(College)
admin.site.register(Student)
admin.site.register(Poster)
admin.site.register(CommonData)

