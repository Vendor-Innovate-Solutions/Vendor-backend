# create_superuser.py
import os
from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "venkatesh")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "venkatesh.k21062005@gmail.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "venkat*2005")

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created")
else:
    print("Superuser already exists")
