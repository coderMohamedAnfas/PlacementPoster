
from io import BytesIO
import os
import zipfile
import requests
import gspread
import re
import time
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib import messages
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from .models import College, Poster, Student, CommonData as cd

def index(request):
    """
    Render the input form for the user to provide details.
    """
   
    # college = College.objects.filter(request.user)  # Assuming `user` is linked to a college
    is_have_sheet = bool( request.user.sheet_url)
    college = College.objects.get(email=request.user.email)
    return render(request, 'index.html',{"is_have_sheet": not is_have_sheet,'name':request.user.name.upper(),'college':college})





# Google API Setup
SERVICE_ACCOUNT_FILE = r"D:\MYCOLLEGEPROJECT\myproject\myapp\exemplary-oath-443817-r8-70c8f3318d19.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)
client = gspread.authorize(creds)

# Global Progress Variable
progress_data = {'progress': 0}

import uuid

# Store progress for each task separately
user_progress = {}

@login_required
def sheet_url_upload(request):
    """Handles Google Sheet URL upload and starts fetching process."""
    if request.method == 'POST':
        sheet_url = request.POST.get('sheet_url')
        print(f"Received Sheet URL: {sheet_url}")

        try:
            college = College.objects.get(email=request.user.email)
            college.sheet_url = sheet_url
            college.save()

            # Generate unique Task ID
            task_id = str(uuid.uuid4())
            user_progress[task_id] = 0  # Initialize progress for this task

            # Start fetching process
            fetch_google_sheet_data(request, task_id)

            # return JsonResponse({"task_id": task_id})
            return JsonResponse({"success": True, "message": "Data fetched successfully!"})

        except College.DoesNotExist:
            return JsonResponse({'error': 'College not found.',"success": False}, status=400)

    return render(request, "sheet_url.html")

def fetch_google_sheet_data(request, task_id):
    """Fetches student data from Google Sheets and updates progress dynamically."""
    user_progress[task_id] = 10  # Start progress

    print(f"Fetching data from Google Sheet for Task ID: {task_id}...")

    try:
        college = College.objects.get(email=request.user.email)
    except College.DoesNotExist:
        return JsonResponse({'error': 'College not found.'}, status=400)

    if not college.sheet_url:
        return JsonResponse({'error': 'Sheet URL is missing.'}, status=400)

    try:
        sheet_id = extract_sheet_id(college.sheet_url)
        user_progress[task_id] = 20

        # Get MIME Type
        mime_type = drive_service.files().get(fileId=sheet_id, fields="mimeType").execute().get('mimeType', '')
        user_progress[task_id] = 30

        # Convert Excel to Google Sheet if needed
        new_sheet_id = sheet_id
        if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            file_metadata = {"name": "Converted Sheet", "mimeType": "application/vnd.google-apps.spreadsheet"}
            converted_file = drive_service.files().copy(fileId=sheet_id, body=file_metadata).execute()
            new_sheet_id = converted_file["id"]
            print(f"✅ Converted Sheet ID: {new_sheet_id}")

        user_progress[task_id] = 50

        # Open Google Sheet
        spreadsheet = client.open_by_key(new_sheet_id)
        worksheet = spreadsheet.sheet1
        data = worksheet.get_all_records()

        if not data:
            return JsonResponse({'error': 'No data found in the sheet.'}, status=400)

        user_progress[task_id] = 60

    except gspread.exceptions.GSpreadException as e:
        college.sheet_url=None
        college.save
        messages.warning(request,"error occured while fetching sheet")
        return JsonResponse({'error': f'Google Sheet Error: {str(e)}'}, status=500)

    # Update Student Data
    DATA = cd.objects.first()
    total_students = len(data)
    processed = 0

    for row in data:
        student, created = Student.objects.update_or_create(
            prn=row.get(DATA.prn_field, ""),
            defaults={
                'name': row.get(DATA.name_field, ""),
                'department': row.get(DATA.department_field, ""),
                'college': college,
            }
        )

        # Process Student Image
        if row.get(DATA.image_field):
            photo_url = transform_google_drive_url(row[DATA.image_field])
            try:
                download_and_save_student_photo(student, photo_url)
            except:
                messages.warning(request,f"{row.get(DATA.prn_field)} is not saved")
        processed += 1
        user_progress[task_id] = int(60 + (processed / total_students) * 40)

    user_progress[task_id] = 100  # Finished
    
    return JsonResponse({'message': 'Students updated successfully.'}, status=200)


@login_required
def fetch_progress(request, task_id):
    """Returns the progress for a given task ID."""
    print(f"✅ Received request for Task ID: {task_id}")  # Debugging

    progress = user_progress.get(task_id, 0)  # Default to 0 if not found

    print(f"Task ID: {task_id}, Progress: {progress}")  # Debugging

    return JsonResponse({'progress': progress})


def transform_google_drive_url(url):
    """Converts Google Drive share links to direct links."""
    match = re.search(r"(?<=id=)[\w-]+", url)
    if match:
        file_id = match.group(0)
        return f"https://drive.google.com/uc?id={file_id}"
    return url  # Return original URL if not a Google Drive link

def download_and_save_student_photo(student, photo_url):
    """Downloads and saves student photos with better error handling."""
    skipped = []
    try:
        response = requests.get(photo_url, stream=True, timeout=10)
        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', ''):
            filename = f"{student.prn}_photo.jpg"
            file_path = os.path.join(settings.MEDIA_ROOT, 'student_photos', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            student.photo = f'student_photos/{filename}'
            student.save()
            print(f"✅ Photo saved for {student.prn}")
        else:
            skipped.append(student.prn)
            print(f"⚠️ Skipped invalid photo for {student.prn}")


    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading photo for {student.prn}: {e}")

def extract_sheet_id(sheet_url):
    """Extracts Google Sheet ID from a given URL."""
    if "/d/" in sheet_url:
        return sheet_url.split("/d/")[1].split("/")[0]
    elif "id=" in sheet_url:
        return sheet_url.split("id=")[1]
    return None








def generate_poster_json(request):
    if request.method == 'POST':
        # Extract form data
        companies = request.POST.getlist('company_name[]')
        lpas = request.POST.getlist('lpa[]')

        # Parse PRNs for each company manually
        prns_dict = {}
        for key in request.POST:
            if key.startswith('prns['):
                # Extract the company index from the key, e.g., prns[0][] -> 0
                company_index = key.split('[')[1].split(']')[0]
                prns_dict[int(company_index)] = request.POST.getlist(key)

        print(f"Companies: {companies}, LPAs: {lpas}, PRNs: {prns_dict}")

        # Prepare a list to store students for the poster
        students_for_poster = []

        # Iterate through each company and corresponding PRNs
        for index, (company, lpa) in enumerate(zip(companies, lpas)):
            prns = prns_dict.get(index, [])
            for prn in prns:
                try:
                    # Get the student by PRN
                    student = Student.objects.get(prn=prn)

                    # Ensure that the student has a photo associated with them
                    student_photo = student.photo if student.photo else 'default_photo.jpg'

                    # Add student data to the list
                    students_for_poster.append({
                        "name": student.name,
                        "company": f"{company} ({lpa} LPA)",
                        "photo": student.photo.url if student.photo else 'default_photo.jpg',
                        "prn": student.prn,
                    })

                except Student.DoesNotExist:
                    messages.error(request, f"Student with PRN {prn} not found.")
                    continue

        # Get the college associated with the logged-in user
        college = College.objects.get(email=request.user.email)

        # Get or create the poster for the college
        poster, created = Poster.objects.get_or_create(college=college)

        # Ensure `data` is not None
        if poster.data is None:
            poster.data = []

        # If poster already exists, merge with existing data
        if not created:
            # Extract existing PRNs from the poster data
            existing_prns = {student['prn'] for student in poster.data}

            # Append only unique students (based on PRN)
            merged_students = [student for student in students_for_poster if student['prn'] not in existing_prns]

            # Update the poster with the merged student list
            poster.data.extend(merged_students)
        else:
            # Assign students_for_poster directly if the poster is newly created
            poster.data = students_for_poster

        # Save the poster
        poster.save()

        # Redirect to a success page or return a JSON response
        messages.success(request,"Placed students details are saved and ready to download")
        return redirect('index')

    return render(request, 'index.html')



from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as authlogin
from django.contrib import messages


def admin_panel(request):
    colleges = College.objects.all()
    return render(request,"admin_user/manage_colleges.html")

def login_view(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']
        print(email,password)
        user = authenticate(request, email=email, password=password)
        print(user)
        if user is not None:
            if user.is_superuser:
                authlogin(request, user)
                return redirect('admin_dash')
            else:
                authlogin(request, user)
                return redirect('index')  # redirect to your desired page after login
        else:
            return render(request, 'login.html', {'error': 'Invalid login credentials'})
    return render(request, 'login.html')




from django.http import JsonResponse
from django.shortcuts import render
from .models import Student

def validate_prn(request):
    prn = request.GET.get('prn', '').strip()
    suggestions = []
    valid = False

    if prn:
        # Check for PRN validity
        valid = Student.objects.filter(prn__iexact=prn).exists()
        
        # Fetch suggestions
        suggestions = Student.objects.filter(prn__startswith=prn).values_list('prn', flat=True)[:5]
        print(suggestions)
    return JsonResponse({'valid': valid, 'suggestions': list(suggestions)})




import csv
import io
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import College

def create_college(request):
    if request.method == "POST":
        if "csv_file" in request.FILES:  # Bulk Upload Logic
            csv_file = request.FILES["csv_file"]
            
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Please upload a valid CSV file.")
                return redirect("manage_colleges")

            try:
                decoded_file = io.StringIO(csv_file.read().decode("utf-8"))
                reader = csv.DictReader(decoded_file)
                
                success_count = 0
                error_count = 0
                colleges_to_create = []

                for row in reader:
                    name = row.get("name")
                    email = row.get("email")
                    
                    if not name or not email:
                        error_count += 1
                        continue  # Skip invalid row

                    if not College.objects.filter(email=email).exists():
                        colleges_to_create.append(
                            College(name=name.strip(), email=email.strip())
                        )
                        success_count += 1
                    else:
                        error_count += 1  # Duplicate email

                College.objects.bulk_create(colleges_to_create)  # Efficient bulk insertion

                messages.success(request, f"Bulk upload completed: {success_count} added, {error_count} skipped.")
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")

        else:  # Individual College Creation Logic
            name = request.POST.get("name")
            email = request.POST.get("email")
            logo = request.FILES.get("logo")
            password = request.POST.get("password") or "123"

            if not (name and email):
                messages.error(request, "Name and Email are required.")
            else:
                try:
                    if not College.objects.filter(email=email).exists():
                        college = College.objects.create_user(name=name, email=email, password=password)
                        if logo:
                            college.logo = logo
                            college.save()

                        messages.success(request, "College created successfully.")
                    else:
                        messages.error(request, "A college with this email already exists.")
                    
                    return redirect('manage_colleges')
                except Exception as e:
                    messages.error(request, f"An error occurred: {e}")

    return redirect("manage_colleges")




from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import College

def edit_college(request, college_id):
    college = get_object_or_404(College, id=college_id)
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        logo = request.FILES.get("logo")

        college.name = name
        college.email = email
        if logo:
            college.logo = logo
        college.save()
        
        messages.success(request, "College updated successfully.")
        return redirect('manage_colleges')

    return render(request, 'admin_user/edit_college.html', {'college': college})

# Delete college
def delete_college(request, college_id):
    college = get_object_or_404(College, id=college_id)
    college.delete()
    messages.success(request, "College deleted successfully.")
    return redirect("manage_colleges")


def manage_colleges(request):
    colleges = College.objects.all()

    if request.method == "POST":
        action = request.POST.get("action")
        college_id = request.POST.get("college_id")

        if action == "delete":
            college = get_object_or_404(College, id=college_id)
            college.delete()
            messages.success(request, f"College {college.name} deleted successfully.")
        elif action == "create":
            name = request.POST.get("name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            
            if not (name and email and password):
                messages.error(request, "All fields are required.")
            else:
                try:
                    College.objects.create_user(email=email, password=password, name=name)
                    messages.success(request, f"College {name} created successfully.")
                except ValueError as e:
                    messages.error(request, str(e))
        return redirect('manage_colleges')

    return render(request, 'admin_user/manage_colleges.html', {'colleges': colleges})


from django.shortcuts import render, redirect, get_object_or_404
from .models import CommonData
from django.contrib import messages
from datetime import datetime
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.contrib import messages
from .models import College

def manage_common_data(request):
    data = CommonData.objects.first()  # Assuming there's only one entry at a time

    if request.method == "POST":
        start_year = request.POST.get("start_year")
        prn_field = request.POST.get("prn_field")
        image_field = request.POST.get("image_field")
        name_field = request.POST.get("name_field")
        department_field = request.POST.get("department_field")

        try:
            # Convert start_year string to a datetime.date object
            start_year_date = datetime.strptime(start_year, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid start year format. Use YYYY-MM-DD.")
            return redirect("common_data")

        if data:  # Update existing CommonData
            data.start_year = start_year_date
            data.prn_field = prn_field
            data.image_field = image_field
            data.name_field = name_field
            data.department_field = department_field
            data.save()
            messages.success(request, "Common data updated successfully.")
        else:  # Create new CommonData
            CommonData.objects.create(
                start_year=start_year_date,
                prn_field=prn_field,
                image_field=image_field,
                name_field=name_field,
                department_field=department_field,
            )
            messages.success(request, "Common data created successfully.")

        return redirect("common_data")

    return render(request, "admin_user/common_data.html", {"data": data})




from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from .models import College

def send_email(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        recipient_list = College.objects.filter(is_superuser=False, is_staff=False).values_list('email', flat=True)

        if recipient_list and subject and message:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email="mohamedanfas7578@gmail.com",
                    recipient_list=list(recipient_list),
                    fail_silently=False,
                )
                messages.success(request, "Emails sent successfully!")
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
        else:
            messages.warning(request, "No valid recipients or message provided.")
        return redirect('sheet_link')  # Redirect back to the email page

    return render(request, 'admin_user/sheet_link.html')  # Render the form if GET request

from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Student, Poster

@login_required
def student_list(request):
    college = request.user
    query = request.GET.get('q')
    
    # Get only students of the logged-in college
    students = Student.objects.filter(college=college).order_by('prn')

    # Search functionality for name or PRN
    if query:
        students = students.filter(name__icontains=query) | students.filter(prn__icontains=query)

    # Get the poster for the logged-in college
    poster = Poster.objects.filter(college=college).first()
    
    # Get placed PRNs from the poster's data (JSON)
    placed_prns = []
    if poster and isinstance(poster.data, list):
        placed_prns = [item['prn'] for item in poster.data if isinstance(item, dict) and 'prn' in item]

    # Pagination: Limit 10 students per page
    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    students = paginator.get_page(page_number)

    context = {
        'students': students,
        'placed_prns': placed_prns,
    }
    return render(request, 'student_list.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import College

@login_required
def profile_view(request):
    college = get_object_or_404(College, email=request.user.email)

    if request.method == 'POST' and 'name' in request.POST:  # Profile update logic
        name = request.POST.get('name')
        email = request.POST.get('email')
        logo = request.FILES.get('logo')

        college.name = name
        college.email = email

        if logo:
            if college.logo and college.logo != "logo.png":
                college.logo.delete(save=False)
            college.logo = logo

        college.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

    return render(request, 'profile.html', {'college': college})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = request.user

        if not user.check_password(old_password):
            messages.error(request, "Current password is incorrect.")
            return redirect('profile')

        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect('profile')

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)  # Keep the user logged in
        messages.success(request, "Password updated successfully!")
        return redirect('profile')

    return redirect('profile')

def update_photo(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST' and request.FILES.get('photo'):
        photo = request.FILES['photo']
        photo.name = f"{student.prn}.jpg"  # Keep PRN format intact
        student.photo = photo
        student.save()
        return JsonResponse({'success': True, 'message': 'Photo updated successfully!'})

    return JsonResponse({'success': False, 'message': 'Error updating photo.'})


from django.shortcuts import render, redirect
from django.contrib import messages
from .models import College, Student, Poster  # Ensure Poster is imported

def clear_students_view(request):
    if request.method == "POST":
        college_ids = request.POST.getlist("college_ids")  # Get selected college IDs

        if not college_ids:
            messages.error(request, "No colleges selected.")
            return redirect("clear_students")  # Redirect back to the same page

        colleges = College.objects.filter(id__in=college_ids, is_superuser=False, is_staff=False)

        # Delete students and posters belonging to the selected colleges
        Student.objects.filter(college__in=colleges).delete()
        Poster.objects.filter(college__in=colleges).delete()

        # Clear sheet_url for selected colleges
        colleges.update(sheet_url=None)

        messages.success(request, "Selected colleges' sheet URLs cleared and corresponding students deleted.")
        return redirect("clear_students")

    # Fetch all colleges except superusers and admins
    colleges = College.objects.filter(is_superuser=False, is_staff=False)
    return render(request, "admin_user/clear_students.html", {"colleges": colleges})



from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from .models import Poster, Student, CommonData
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from django.contrib import messages
from reportlab.pdfgen.pathobject import PDFPathObject as Path  # Import Path for clipping
import math
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas


def draw_college_name(pdf, college_name, x, y, max_width):
    font_size = 18  # Start with a larger font size
    pdf.setFont("Helvetica-Bold", font_size)

    # Reduce font size if text width exceeds max_width
    while pdf.stringWidth(college_name, "Helvetica-Bold", font_size) > max_width and font_size > 13:
        font_size -= 1
        pdf.setFont("Helvetica-Bold", font_size)

    # If still too long, split into multiple lines
    if pdf.stringWidth(college_name, "Helvetica-Bold", font_size) > max_width:
        words = college_name.split()
        line1, line2 = "", ""

        for word in words:
            if pdf.stringWidth(line1 + word, "Helvetica-Bold", font_size) < max_width:
                line1 += word + " "
            else:
                line2 += word + " "

        pdf.drawCentredString(x, y+10, line1.strip())
        pdf.drawCentredString(x, y - 5, line2.strip())  # Adjust spacing for second line
    else:
        pdf.drawCentredString(x, y, college_name)

def draw_full_page_background_pattern(pdf, page_width, page_height, pattern_style):
    """
    Draws a full-page background pattern with various styles.

    Parameters:
    - pdf: Canvas object to draw on
    - page_width: Width of the page
    - page_height: Height of the page
    - pattern_style: Dictionary containing background pattern parameters
      Expected keys:
      - 'base_color': Base background color
      - 'pattern_color': Color for pattern elements
      - 'pattern_type': Type of pattern ('diagonal_lines', 'dots', 'grid', 'waves', 'gradient')
    """
    # Validate input
    if not all(key in pattern_style for key in ['base_color', 'pattern_color', 'pattern_type']):
        raise ValueError("pattern_style must contain 'base_color', 'pattern_color', and 'pattern_type'")

    base_color = pattern_style['base_color']
    pattern_color = pattern_style['pattern_color']
    pattern_type = pattern_style['pattern_type']

    # First, fill the entire page with base color
    pdf.setFillColor(base_color)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    # Draw different pattern types
    if pattern_type == 'diagonal_lines':
        pdf.setStrokeColor(pattern_color)
        pdf.setLineWidth(0.3)
        pdf.setDash([3, 5])
        line_spacing = 20
        for i in range(int((page_width + page_height) / line_spacing) + 1):
            pdf.line(
                i * line_spacing, 0,
                0, i * line_spacing
            )
            pdf.line(
                page_width - i * line_spacing, page_height,
                page_width, page_height - i * line_spacing
            )
        pdf.setDash([])

    elif pattern_type == 'dots':
        pdf.setFillColor(pattern_color)
        pdf.setStrokeColor(pattern_color)
        dot_spacing = 30
        dot_size = 1
        for i in range(0, int(page_width/dot_spacing) + 2):
            for j in range(0, int(page_height/dot_spacing) + 2):
                pdf.circle(
                    i * dot_spacing,
                    j * dot_spacing,
                    dot_size, fill=1
                )

    elif pattern_type == 'grid':
        pdf.setStrokeColor(pattern_color)
        pdf.setLineWidth(0.2)
        pdf.setDash([1, 4])
        grid_spacing = 20
        # Vertical lines
        for i in range(0, int(page_width / grid_spacing) + 1):
            pdf.line(i * grid_spacing, 0, i * grid_spacing, page_height)
        # Horizontal lines
        for j in range(0, int(page_height / grid_spacing) + 1):
            pdf.line(0, j * grid_spacing, page_width, j * grid_spacing)
        pdf.setDash([])

    elif pattern_type == 'waves':
        pdf.setStrokeColor(pattern_color)
        pdf.setLineWidth(0.5)
        wave_spacing = 30
        amplitude = 10
        # Vertical waves
        for i in range(0, int(page_width / wave_spacing) + 1):
            path = pdf.beginPath()
            path.moveTo(i * wave_spacing, 0)
            for j in range(0, int(page_height) + 1, 5):
                x_offset = math.sin(j * 0.05) * amplitude
                path.lineTo(i * wave_spacing + x_offset, j)
            pdf.drawPath(path, stroke=1, fill=0)

    elif pattern_type == 'gradient':
        # Create a smooth gradient background
        gradient_steps = 50
        for i in range(gradient_steps):
            # Interpolate between two colors
            color = Color(
                base_color.red + (pattern_color.red - base_color.red) * (i / gradient_steps),
                base_color.green + (pattern_color.green - base_color.green) * (i / gradient_steps),
                base_color.blue + (pattern_color.blue - base_color.blue) * (i / gradient_steps)
            )
            pdf.setFillColor(color)
            pdf.rect(
                0,
                (page_height / gradient_steps) * i,
                page_width,
                page_height / gradient_steps,
                fill=1,
                stroke=0
            )



def draw_company_name(pdf, company_name, x, y, max_width):
    font_size = 11
    pdf.setFont("Helvetica-Bold", font_size)

    # Try to fit in one line by reducing font size
    while pdf.stringWidth(company_name, "Helvetica-Bold", font_size) > max_width and font_size > 6:
        font_size -= 1
        pdf.setFont("Helvetica-Bold", font_size)

    # If still too long, break it into two lines
    if pdf.stringWidth(company_name, "Helvetica-Bold", font_size) > max_width:
        words = company_name.split()
        line1, line2 = "", ""

        for word in words:
            if pdf.stringWidth(line1 + word, "Helvetica-Bold", font_size) < max_width:
                line1 += word + " "
            else:
                line2 += word + " "

        pdf.drawCentredString(x, y, line1.strip())
        pdf.drawCentredString(x, y - 10, line2.strip())  # Second line below
    else:
        pdf.drawCentredString(x, y, company_name)


def draw_circular_image(pdf, img, x, y, diameter, company_color):
    """Draws an image with a circular mask."""
    # Create a circular path
    path = Path()
    path.moveTo(x + diameter / 2, y)
    path.arcTo(x, y, x + diameter, y + diameter, 0, 360)
    path.close()

    # Save state before clipping
    pdf.saveState()
    pdf.clipPath(path, stroke=0, fill=0)

    # Use company color for the inner ring
    pdf.setStrokeColor(company_color)
    pdf.setLineWidth(2)
    pdf.circle(x + diameter / 2, y + diameter / 2, diameter / 2 + 2, stroke=1, fill=0)

    try:
        pdf.drawImage(img, x, y, width=diameter, height=diameter, mask='auto')

    except Exception as e:
        print(f"Error loading student photo: {e}")
        pdf.setFillColorRGB(0.6, 0.31, 0.3)  # Placeholder color
        pdf.circle(x + diameter / 2, y + diameter / 2, diameter / 2, fill=1)

    # Draw the circular border (using company color)
    pdf.setStrokeColor(company_color)
    pdf.setLineWidth(11)
    pdf.circle(x + diameter / 2, y + diameter / 2, (diameter / 2) + 3, stroke=1, fill=0)

    # Restore canvas state
    pdf.restoreState()


def draw_gradient_background(pdf, page_width, page_height):
    """Draws a smooth gradient background from dark to light blue."""
    gradient_steps = 20  # More steps = smoother gradient
    for i in range(gradient_steps):
        color = colors.linearlyInterpolatedColor(
            HexColor("#000280"),  # Deep Gold (Top-left)
            HexColor("#000200"),   # Soft Sky Blue (Bottom)
            0, 1, i / gradient_steps
        )
        pdf.setFillColor(color)
        pdf.rect(0, (page_height / gradient_steps) * i,
                 page_width, page_height / gradient_steps, fill=1, stroke=0)


def get_company_colors(index):
    """Returns a color pair (background, foreground) for a company based on index."""
    # Define a list of company color pairs (background, foreground)
    company_colors = [
        (HexColor("#e8890c"), HexColor("#ffffff")),  # Orange BG, White FG
        (HexColor("#1a5276"), HexColor("#ffffff")),  # Navy Blue BG, White FG
        (HexColor("#27ae60"), HexColor("#ffffff")),  # Green BG, White FG
        (HexColor("#8e44ad"), HexColor("#ffffff")),  # Purple BG, White FG
        (HexColor("#c0392b"), HexColor("#ffffff")),  # Red BG, White FG
        (HexColor("#2c3e50"), HexColor("#ffffff")),  # Dark Gray BG, White FG
        (HexColor("#d35400"), HexColor("#ffffff")),  # Burnt Orange BG, White FG
        (HexColor("#16a085"), HexColor("#ffffff")),  # Teal BG, White FG
        (HexColor("#7d3c98"), HexColor("#ffffff")),  # Dark Purple BG, White FG
        (HexColor("#a47723"), HexColor("#ffffff")),  # Gold BG, White FG
    ]

    # Return a color pair based on the index
    return company_colors[index % len(company_colors)]


def generate_poster_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponse("Unauthorized", status=401)

    # Get common data
    cd = CommonData.objects.first()

    # Fetch poster for the logged-in college
    try:
        poster = get_object_or_404(Poster, college=request.user)
    except:
        messages.error(request, "Error: Please Insert Atleast One Placed Student")
        return redirect('index')

    poster_data = poster.data  # JSON field containing company and PRN data
    college_name = request.user.name

    page_background_styles = {
        'diagonal_lines': {
            'base_color': HexColor("#f0f0f0"),
            'pattern_color': HexColor("#e0e0e0"),
            'pattern_type': 'diagonal_lines'
        },
        'dots': {
            'base_color': HexColor("#f5f5f5"),
            'pattern_color': HexColor("#e5e5e5"),
            'pattern_type': 'dots'
        },
        'grid': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'grid'
        },
        'waves': {
            'base_color': HexColor("#f8f8f8"),
            'pattern_color': HexColor("#e8e8f8"),
            'pattern_type': 'waves'
        },
        'gradient': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'gradient'
        }
    }
    # PDF configuration
    page_width, page_height = A4
    margin = 30
    image_size = 77
    student_spacing = 33
    company_spacing = 25
    max_x = page_width
    students_per_row = 5

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    draw_gradient_background(pdf, page_width, page_height)
    pdf.setTitle(college_name)

    # Background color (Light Grey)
    pdf.setFillColor(HexColor("#f5ede4"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    # Load college logo
    try:
        college_logo = ImageReader(request.user.logo.path)
    except Exception as e:
        print(f"Error loading college logo: {e}")
        college_logo = None

    def draw_header_footer():

        background_style = page_background_styles["waves"]

        # Draw full-page background pattern before other elements
        draw_full_page_background_pattern(pdf, page_width, page_height, background_style)
        """ Draws header and footer on each page """
        pdf.setFillColor(HexColor("#a47723"))  # Navy blue
        pdf.rect(0, page_height - 93, page_width, 180, fill=1, stroke=0)

        pdf.setStrokeColor(HexColor("#a47723"))  # Gold
        pdf.rect(margin - 10, margin - 15, page_width - (2 * margin) + 20, page_height - 30)

        pdf.setFillColor(HexColor("#ffffff"))  # Gold text
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(page_width / 2, page_height - 38, "STATE PLACEMENT CELL")
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(page_width / 2, page_height - 50, "Government and Government Aided Polytechnic Colleges, Kerala")
        pdf.line(30, page_height - 55, page_width - 30, page_height - 55)

        pdf.setFont("Helvetica-Bold", 18)
        draw_college_name(pdf, college_name, page_width / 2, page_height - 80, max_width=page_width-170)
        # pdf.drawCentredString(page_width / 2, page_height - 80, college_name.upper())
        pdf.line(110, page_height - 93, page_width - 33, page_height - 93)
        pdf.line(30, page_height - 130, page_width - 30, page_height - 130)

        pdf.setFillColorRGB(0, 0, 0.15)  # Deep Navy
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(page_width / 2, page_height - 150, f"CAMPUS PLACEMENT {cd.start_year.year} - {cd.end_year.year}")
        pdf.line(30, page_height - 155, page_width - 30, page_height - 155)

        if college_logo:
            pdf.drawImage(college_logo, 20, page_height - 75, width=60, height=60, mask='auto')

    x, y = margin + 9, page_height - 280
    draw_header_footer()

    all_students = []
    # Dictionary to track company indices for consistent colors
    company_indices = {}
    company_index = 0

    for entry in poster_data:
        company_name = entry.get('company', 'Unknown Company')
        prn = entry.get('prn')
        if not prn:
            continue

        # Assign index to company if not already assigned
        if company_name not in company_indices:
            company_indices[company_name] = company_index
            company_index += 1

        try:
            student = Student.objects.get(prn=prn, college=poster.college)
            all_students.append({
                'student': student,
                'company': company_name,
                'company_index': company_indices[company_name]
            })
        except Student.DoesNotExist:
            print(f"Student with PRN {prn} not found.")

    current_company = None
    students_in_current_row = 0
    company_start_x = None
    company_start_y = None
    current_company_index = None
    current_bg_color = None
    current_fg_color = None

    for index, student_data in enumerate(all_students):
        student = student_data['student']
        company = student_data['company']
        company_index = student_data['company_index']

        # Start a new company block
        if current_company != company:
            if current_company is not None:
                # Draw the border for the previous company
                width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
                pdf.setStrokeColor(current_bg_color)  # Use company color for border
                pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

                # Display company name above the group
                pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
                pdf.setFont("Helvetica-Bold", 11)
                draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Reset values for the new company
            company_start_x = x
            company_start_y = y
            students_in_current_row = 0
            current_company = company
            current_company_index = company_index
            current_bg_color, current_fg_color = get_company_colors(current_company_index)

        # Move to a new row if space exceeds
        if students_in_current_row >= students_per_row or x + image_size  > max_x-10:
            # Draw the border for the previous row's company
            width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
            pdf.setStrokeColor(current_bg_color)  # Use company color for border
            pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

            pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
            pdf.setFont("Helvetica-Bold", 11)
            draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Start a new row
            x = margin + 9
            y -= (image_size + 90)

            if y < margin + 10:
                pdf.showPage()
                draw_header_footer()
                x = margin + 9
                y = page_height - 280

            company_start_x = x
            company_start_y = y
            students_in_current_row = 0

        # Draw student photo with company color
        try:
            img = ImageReader(student.photo.path)
            draw_circular_image(pdf, img, x, y, image_size, current_bg_color)
        except Exception as e:
            print(f"Error loading student photo for {student.name}: {e}")
            pdf.setFillColorRGB(0.6, 0.31, 0.3)
            pdf.circle(x + image_size / 2, y + image_size / 2, image_size / 2, fill=1)

        # Define name background dimensions
        name_bg_width = image_size + 10
        name_bg_height = 18  # Height for the name background
        name_bg_y = y - 20  # Position the name background rectangle

        # Draw background for student name using company color
        pdf.setFillColor(current_bg_color)  # Use company color
        pdf.roundRect(x - 5, name_bg_y-8, name_bg_width, name_bg_height+7, 5, fill=1, stroke=0)

        # Draw student name
        student_name = student.name
        font_size = 7
        pdf.setFillColor(current_fg_color)  # Use company foreground color
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y + 5, student_name)

        # Draw student department below the name
        pdf.setFont("Helvetica", 6)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y - 5, student.department)

        # Update positions
        students_in_current_row += 1
        x += image_size + student_spacing

    # Draw the final company's border
    if current_company is not None:
        width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
        pdf.setStrokeColor(current_bg_color)  # Use company color for border
        pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

        pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
        pdf.setFont("Helvetica-Bold", 11)
        draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=placement_poster.pdf"  # Use 'inline' to show in iframe
    return response

def download_posters_page(request):
    posters = Poster.objects.filter(college__is_superuser=False)
    return render(request, 'admin_user/download_posters.html', {'posters': posters})


import zipfile
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.shortcuts import get_object_or_404
from .models import Poster, College, Student, CommonData
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

def generate_poster_pdf_for_zip(poster):
    """Generate PDF for a given poster and return a BytesIO buffer."""
    print(poster)
    college = poster.college
    poster_data = poster.data  # JSON data (companies & PRNs)
    print(poster_data)
    cd = CommonData.objects.first()

    # Fetch poster for the logged-in college
    # try:
    #     poster = get_object_or_404(Poster, college=college)
    # except:
    #     messages.error(request, "Error: Please Insert Atleast One Placed Student")
    #     return redirect('index')

    # poster_data = poster.data  # JSON field containing company and PRN data
    college_name = college.name

    page_background_styles = {
        'diagonal_lines': {
            'base_color': HexColor("#f0f0f0"),
            'pattern_color': HexColor("#e0e0e0"),
            'pattern_type': 'diagonal_lines'
        },
        'dots': {
            'base_color': HexColor("#f5f5f5"),
            'pattern_color': HexColor("#e5e5e5"),
            'pattern_type': 'dots'
        },
        'grid': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'grid'
        },
        'waves': {
            'base_color': HexColor("#f8f8f8"),
            'pattern_color': HexColor("#e8e8f8"),
            'pattern_type': 'waves'
        },
        'gradient': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'gradient'
        }
    }
    # PDF configuration
    page_width, page_height = A4
    margin = 30
    image_size = 77
    student_spacing = 33
    company_spacing = 25
    max_x = page_width
    students_per_row = 5

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    draw_gradient_background(pdf, page_width, page_height)
    pdf.setTitle(college_name)

    # Background color (Light Grey)
    pdf.setFillColor(HexColor("#f5ede4"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    # Load college logo
    try:
        college_logo = ImageReader(college.logo.path)
    except Exception as e:
        print(f"Error loading college logo: {e}")
        college_logo = None

    def draw_header_footer():

        background_style = page_background_styles["waves"]

        # Draw full-page background pattern before other elements
        draw_full_page_background_pattern(pdf, page_width, page_height, background_style)
        """ Draws header and footer on each page """
        pdf.setFillColor(HexColor("#a47723"))  # Navy blue
        pdf.rect(0, page_height - 93, page_width, 180, fill=1, stroke=0)

        pdf.setStrokeColor(HexColor("#a47723"))  # Gold
        pdf.rect(margin - 10, margin - 15, page_width - (2 * margin) + 20, page_height - 30)

        pdf.setFillColor(HexColor("#ffffff"))  # Gold text
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(page_width / 2, page_height - 38, "STATE PLACEMENT CELL")
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(page_width / 2, page_height - 50, "Government and Government Aided Polytechnic Colleges, Kerala")
        pdf.line(30, page_height - 55, page_width - 30, page_height - 55)

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(page_width / 2, page_height - 80, college_name.upper())
        pdf.line(110, page_height - 93, page_width - 33, page_height - 93)
        pdf.line(30, page_height - 130, page_width - 30, page_height - 130)

        pdf.setFillColorRGB(0, 0, 0.15)  # Deep Navy
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(page_width / 2, page_height - 150, f"CAMPUS PLACEMENT {cd.start_year.year} - {cd.end_year.year}")
        pdf.line(30, page_height - 155, page_width - 30, page_height - 155)

        if college_logo:
            pdf.drawImage(college_logo, 30, page_height - 75, width=60, height=60, mask='auto')

    x, y = margin + 9, page_height - 280
    draw_header_footer()

    all_students = []
    # Dictionary to track company indices for consistent colors
    company_indices = {}
    company_index = 0

    for entry in poster_data:
        company_name = entry.get('company', 'Unknown Company')
        prn = entry.get('prn')
        if not prn:
            continue

        # Assign index to company if not already assigned
        if company_name not in company_indices:
            company_indices[company_name] = company_index
            company_index += 1

        try:
            student = Student.objects.get(prn=prn, college=poster.college)
            all_students.append({
                'student': student,
                'company': company_name,
                'company_index': company_indices[company_name]
            })
        except Student.DoesNotExist:
            print(f"Student with PRN {prn} not found.")

    current_company = None
    students_in_current_row = 0
    company_start_x = None
    company_start_y = None
    current_company_index = None
    current_bg_color = None
    current_fg_color = None

    for index, student_data in enumerate(all_students):
        student = student_data['student']
        company = student_data['company']
        company_index = student_data['company_index']

        # Start a new company block
        if current_company != company:
            if current_company is not None:
                # Draw the border for the previous company
                width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
                pdf.setStrokeColor(current_bg_color)  # Use company color for border
                pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

                # Display company name above the group
                pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
                pdf.setFont("Helvetica-Bold", 11)
                draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Reset values for the new company
            company_start_x = x
            company_start_y = y
            students_in_current_row = 0
            current_company = company
            current_company_index = company_index
            current_bg_color, current_fg_color = get_company_colors(current_company_index)

        # Move to a new row if space exceeds
        if students_in_current_row >= students_per_row or x + image_size  > max_x-10:
            # Draw the border for the previous row's company
            width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
            pdf.setStrokeColor(current_bg_color)  # Use company color for border
            pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

            pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
            pdf.setFont("Helvetica-Bold", 11)
            draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Start a new row
            x = margin + 9
            y -= (image_size + 90)

            if y < margin + 10:
                pdf.showPage()
                draw_header_footer()
                x = margin + 9
                y = page_height - 280

            company_start_x = x
            company_start_y = y
            students_in_current_row = 0

        # Draw student photo with company color
        try:
            img = ImageReader(student.photo.path)
            draw_circular_image(pdf, img, x, y, image_size, current_bg_color)
        except Exception as e:
            print(f"Error loading student photo for {student.name}: {e}")
            pdf.setFillColorRGB(0.6, 0.31, 0.3)
            pdf.circle(x + image_size / 2, y + image_size / 2, image_size / 2, fill=1)

        # Define name background dimensions
        name_bg_width = image_size + 10
        name_bg_height = 18  # Height for the name background
        name_bg_y = y - 20  # Position the name background rectangle

        # Draw background for student name using company color
        pdf.setFillColor(current_bg_color)  # Use company color
        pdf.roundRect(x - 5, name_bg_y-8, name_bg_width, name_bg_height+7, 5, fill=1, stroke=0)

        # Draw student name
        student_name = student.name
        font_size = 7
        pdf.setFillColor(current_fg_color)  # Use company foreground color
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y + 5, student_name)

        # Draw student department below the name
        pdf.setFont("Helvetica", 6)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y - 5, student.department)

        # Update positions
        students_in_current_row += 1
        x += image_size + student_spacing

    # Draw the final company's border
    if current_company is not None:
        width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
        pdf.setStrokeColor(current_bg_color)  # Use company color for border
        pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

        pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
        pdf.setFont("Helvetica-Bold", 11)
        draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    # response = HttpResponse(buffer, content_type="application/pdf")
    # response["Content-Disposition"] = "inline; filename=placement_poster.pdf"  # Use 'inline' to show in iframe
    # return response
    return buffer

def download_all_posters_zip(request):
    """Generate and return a ZIP file containing PDFs of all posters."""
    posters = Poster.objects.all()
    
    if not posters.exists():
        messages.warning(request,"No posters available")
        return HttpResponse("No posters available.", content_type="text/plain")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for poster in posters:
            pdf_buffer = generate_poster_pdf_for_zip(poster)
            file_name = f"{poster.college.name.replace(' ', '_')}_poster.pdf"
            zip_file.writestr(file_name, pdf_buffer.getvalue())

    zip_buffer.seek(0)

    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="all_posters.zip"'
    return response



def download_individual_poster(request, poster_id):
    poster = get_object_or_404(Poster,id=poster_id)
    # poster = get_object_or_404(Poster, college=request.user)
    # poster = get_object_or_404(Poster,id=poster_id)
    
    college = College.objects.get(email=poster.college.email)
    # Extract dynamic data (companies and PRNs) from the 'data' field of the Poster model
    poster_data = poster.data  # This is a JSON field, so we get a Python dict


    cd = CommonData.objects.first()

    # Fetch poster for the logged-in college
 
    # poster_data = poster.data  # JSON field containing company and PRN data
    college_name = college.name

    page_background_styles = {
        'diagonal_lines': {
            'base_color': HexColor("#f0f0f0"),
            'pattern_color': HexColor("#e0e0e0"),
            'pattern_type': 'diagonal_lines'
        },
        'dots': {
            'base_color': HexColor("#f5f5f5"),
            'pattern_color': HexColor("#e5e5e5"),
            'pattern_type': 'dots'
        },
        'grid': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'grid'
        },
        'waves': {
            'base_color': HexColor("#f8f8f8"),
            'pattern_color': HexColor("#e8e8f8"),
            'pattern_type': 'waves'
        },
        'gradient': {
            'base_color': HexColor("#ffffff"),
            'pattern_color': HexColor("#f0f0f0"),
            'pattern_type': 'gradient'
        }
    }
    # PDF configuration
    page_width, page_height = A4
    margin = 30
    image_size = 77
    student_spacing = 33
    company_spacing = 25
    max_x = page_width
    students_per_row = 5

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    draw_gradient_background(pdf, page_width, page_height)
    pdf.setTitle(college_name)

    # Background color (Light Grey)
    pdf.setFillColor(HexColor("#f5ede4"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    # Load college logo
    try:
        college_logo = ImageReader(college.logo.path)
    except Exception as e:
        print(f"Error loading college logo: {e}")
        college_logo = None

    def draw_header_footer():

        background_style = page_background_styles["waves"]

        # Draw full-page background pattern before other elements
        draw_full_page_background_pattern(pdf, page_width, page_height, background_style)
        """ Draws header and footer on each page """
        pdf.setFillColor(HexColor("#a47723"))  # Navy blue
        pdf.rect(0, page_height - 93, page_width, 180, fill=1, stroke=0)

        pdf.setStrokeColor(HexColor("#a47723"))  # Gold
        pdf.rect(margin - 10, margin - 15, page_width - (2 * margin) + 20, page_height - 30)

        pdf.setFillColor(HexColor("#ffffff"))  # Gold text
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(page_width / 2, page_height - 38, "STATE PLACEMENT CELL")
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(page_width / 2, page_height - 50, "Government and Government Aided Polytechnic Colleges, Kerala")
        pdf.line(30, page_height - 55, page_width - 30, page_height - 55)

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(page_width / 2, page_height - 80, college_name.upper())
        pdf.line(110, page_height - 93, page_width - 33, page_height - 93)
        pdf.line(30, page_height - 130, page_width - 30, page_height - 130)

        pdf.setFillColorRGB(0, 0, 0.15)  # Deep Navy
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(page_width / 2, page_height - 150, f"CAMPUS PLACEMENT {cd.start_year.year} - {cd.end_year.year}")
        pdf.line(30, page_height - 155, page_width - 30, page_height - 155)

        if college_logo:
            pdf.drawImage(college_logo, 30, page_height - 75, width=60, height=60, mask='auto')

    x, y = margin + 9, page_height - 280
    draw_header_footer()

    all_students = []
    # Dictionary to track company indices for consistent colors
    company_indices = {}
    company_index = 0

    for entry in poster_data:
        company_name = entry.get('company', 'Unknown Company')
        prn = entry.get('prn')
        if not prn:
            continue

        # Assign index to company if not already assigned
        if company_name not in company_indices:
            company_indices[company_name] = company_index
            company_index += 1

        try:
            student = Student.objects.get(prn=prn, college=poster.college)
            all_students.append({
                'student': student,
                'company': company_name,
                'company_index': company_indices[company_name]
            })
        except Student.DoesNotExist:
            print(f"Student with PRN {prn} not found.")

    current_company = None
    students_in_current_row = 0
    company_start_x = None
    company_start_y = None
    current_company_index = None
    current_bg_color = None
    current_fg_color = None

    for index, student_data in enumerate(all_students):
        student = student_data['student']
        company = student_data['company']
        company_index = student_data['company_index']

        # Start a new company block
        if current_company != company:
            if current_company is not None:
                # Draw the border for the previous company
                width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
                pdf.setStrokeColor(current_bg_color)  # Use company color for border
                pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

                # Display company name above the group
                pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
                pdf.setFont("Helvetica-Bold", 11)
                draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Reset values for the new company
            company_start_x = x
            company_start_y = y
            students_in_current_row = 0
            current_company = company
            current_company_index = company_index
            current_bg_color, current_fg_color = get_company_colors(current_company_index)

        # Move to a new row if space exceeds
        if students_in_current_row >= students_per_row or x + image_size  > max_x-10:
            # Draw the border for the previous row's company
            width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
            pdf.setStrokeColor(current_bg_color)  # Use company color for border
            pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

            pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
            pdf.setFont("Helvetica-Bold", 11)
            draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

            # Start a new row
            x = margin + 9
            y -= (image_size + 90)

            if y < margin + 10:
                pdf.showPage()
                draw_header_footer()
                x = margin + 9
                y = page_height - 280

            company_start_x = x
            company_start_y = y
            students_in_current_row = 0

        # Draw student photo with company color
        try:
            img = ImageReader(student.photo.path)
            draw_circular_image(pdf, img, x, y, image_size, current_bg_color)
        except Exception as e:
            print(f"Error loading student photo for {student.name}: {e}")
            pdf.setFillColorRGB(0.6, 0.31, 0.3)
            pdf.circle(x + image_size / 2, y + image_size / 2, image_size / 2, fill=1)

        # Define name background dimensions
        name_bg_width = image_size + 10
        name_bg_height = 18  # Height for the name background
        name_bg_y = y - 20  # Position the name background rectangle

        # Draw background for student name using company color
        pdf.setFillColor(current_bg_color)  # Use company color
        pdf.roundRect(x - 5, name_bg_y-8, name_bg_width, name_bg_height+7, 5, fill=1, stroke=0)

        # Draw student name
        student_name = student.name
        font_size = 7
        pdf.setFillColor(current_fg_color)  # Use company foreground color
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y + 5, student_name)

        # Draw student department below the name
        pdf.setFont("Helvetica", 6)
        pdf.drawCentredString(x + (image_size / 2), name_bg_y - 5, student.department)

        # Update positions
        students_in_current_row += 1
        x += image_size + student_spacing

    # Draw the final company's border
    if current_company is not None:
        width = (students_in_current_row * (image_size + student_spacing)) - student_spacing
        pdf.setStrokeColor(current_bg_color)  # Use company color for border
        pdf.rect(company_start_x - 10, company_start_y - 40, width + 20, image_size + 80)

        pdf.setFillColor(HexColor("#333333"))  # Dark Grey Text
        pdf.setFont("Helvetica-Bold", 11)
        draw_company_name(pdf, current_company, company_start_x + (width / 2), company_start_y + image_size + 20, width)

   
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type="application/pdf")


def edit_student(request, pk):
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        student.name = request.POST['name']
        student.department = request.POST['department']
        student.save()
        messages.success(request, 'Student details updated successfully!')
        return redirect('student_list')

    return render(request, 'edit_student.html', {'student': student})

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('login')  # Redirect to the login page after logout

from django.contrib.auth.views import PasswordResetConfirmView
from django.shortcuts import redirect

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    def get(self, request, *args, **kwargs):
        print(f"✅ Received reset request for: {kwargs}")  # Debug
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        return redirect('password_reset_complete')  # Force redirection
