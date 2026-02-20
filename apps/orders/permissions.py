from rest_framework.permissions import BasePermission


class CanApproveOrder(BasePermission):

    def has_permission(self, request, view):
        if request.method in ["PUT", "PATCH"]:
            if request.data.get("status") == "approved":
                return request.user.is_admin or request.user.is_office
        return True
