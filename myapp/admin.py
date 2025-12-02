from django.contrib import admin

# Register your models here.
from .models import College, Student,CommonData,Company,PlacementData,Year

admin.site.register(College)
admin.site.register(Student)
admin.site.register(Company)
admin.site.register(CommonData)
admin.site.register(Year)

