from rest_framework import viewsets, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from .serializers import AdminUserProfileSerializer, ProfileSerializer
from .models import AdminUserProfile, Profile

User = get_user_model()

# class ProfileViewSet(viewsets.ModelViewSet):
#     queryset = User.objects.all()
#     serializer_class = ProfileSerializer

#     def create(self, request, *args, **kwargs):
#         # Remove password if present
#         data = request.data.copy()
#         data.pop("password", None)

#         serializer = self.get_serializer(data=data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.save()

#         # Set a random temporary password
#         temp_password = User.objects.make_random_password()
#         user.set_password(temp_password)
#         user.save()

#         # Send password setup email
#         token = default_token_generator.make_token(user)
#         reset_link = f"{request.scheme}://{request.get_host()}/reset-password/{user.pk}/{token}/"
#         send_mail(
#             "Set Your Password",
#             f"Hello {user.username},\n\nPlease set your password using this link:\n{reset_link}",
#             "no-reply@yourdomain.com",
#             [user.email],
#         )

#         headers = self.get_success_headers(serializer.data)
#         return Response(
#             {
#                 "user": serializer.data,
#                 "message": "Customer created. Password setup email sent."
#             },
#             status=status.HTTP_201_CREATED,
#             headers=headers
#         )

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

class AdminUserProfileViewSet(viewsets.ModelViewSet):
    queryset = AdminUserProfile.objects.all()
    serializer_class = AdminUserProfileSerializer
