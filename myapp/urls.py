from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
urlpatterns = [
     path('', views.login_view, name='login'),
    path('generate-poster/', views.index, name='index'),  # Home page with the form
   #  path('save/',views.generate_poster_json,name='generate_poster'),
     path('profile/', views.profile_view, name='profile'),
    # path('poster/<int:poster_id>/download/', views.download_poster, name='download_poster'),

    path('poster/download/',views.generate_poster_pdf, name='generate_poster'),



    path('import-sheet/', views.sheet_url_upload, name='sheet_url_upload'),
   path('upload-excel/', views.upload_excel, name='upload_excel'),


    # path('upload-sheet-url/',views.sheet_url_upload,name="sheet_url_upload"),
    path('admin-panel/',views.admin_panel,name="admin_dash"),
  path("clear-students/", views.clear_students_view, name="clear_students"),
# path('download-posters/', views.download_posters_page, name='download_posters'),

path('send-sheet-link/', views.send_email, name='sheet_link'),
    path('validate-prn/', views.validate_prn, name='validate_prn'),
     path('manage-college/', views.manage_colleges, name='manage_colleges'),
path('common-data/', views.manage_common_data, name='common_data'),

     path('download-posters/', views.download_posters_page, name='download_posters'),
    # path('download-poster/<int:poster_id>/', views.download_individual_poster, name='download_individual_poster'),
      path('download/pdf/<int:college_id>/', views.download_college_pdf, name='download_college_pdf'),
       path('download/all-college-pdfs/', views.download_all_college_pdfs, name='download_all_college_pdfs'),
    # path('download-all-posters/', views.download_all_posters_zip, name='download_bulk_posters'),
path('delete-college/<int:college_id>/', views.delete_college, name='delete_college'),
 path('create-college/', views.create_college, name='create_college'),
  path('edit/<int:college_id>/', views.edit_college, name='edit_college'),
   path('verify_and_fetch_data',views.fetch_google_sheet_data,name="verify_and_fetch_data"),

path('students/', views.student_list, name='student_list'),

 path('students/edit/<int:pk>/', views.edit_student, name='edit_student'),
 path('students/update-photo/<int:pk>/', views.update_photo, name='update_photo'),
  path('logout/', views.logout_view, name='logout'),
      path('change-password/', views.change_password_view, name='change_password'),
       path('password-reset/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
   path('reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
 path('delete-all-students/', views.delete_all_students, name='delete_all_students'),
    path('delete-poster/', views.delete_poster, name='delete_poster'),

  path('companies/', views.company_list_view, name='company_list'),
    path('companies/add-company/', views.add_company_post, name='add_company_post'),
     path('companies/edit/<int:company_id>/', views.edit_company_post, name='edit_company_post'),
    path('companies/delete/<int:company_id>/', views.delete_company, name='delete_company'),
    # path('download-placements/', views.download_excel, name='download_excel'),s
path('download-poster-pdf/', views.download_placement_pdf, name='download_poster_pdf'),
    path('CollegeWiseCompanies/', views.company_students_view, name='company_students'),
    path('companies/<int:company_id>/students/', views.get_students_for_company, name='get_students_for_company'),
    path('students/<int:student_id>/download-photo/', views.download_student_photo, name='download_student_photo'),
 path("add_placement_view/",views.add_placement_view,name="add_placement"),    
     path('remove_student/', views.remove_student_from_placement, name='remove_student_from_placement'),
 path('companies/<int:company_id>/add-student/', views.add_student_to_company, name='add_student_to_company'),
path('add-student/', views.add_student, name='add_student'),



 path('get-sheet-headers/', views.get_sheet_headers, name='get_sheet_headers'),

    # Endpoint to process header mapping and save CommonData
    path('map-sheet-headers/', views.map_sheet_headers, name='map_headers_and_import'),
]



