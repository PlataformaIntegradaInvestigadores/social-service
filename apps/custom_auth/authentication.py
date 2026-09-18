from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.custom_auth.identity_principal import principal_from_token
from apps.jobs.domain.entities.company import Company


class DualUserJWTAuthentication(JWTAuthentication):
    """
    Autenticación JWT que puede manejar tanto usuarios como empresas
    basándose en el contenido del token.
    """

    def authenticate(self, request):
        """
        Sobrescribe el método authenticate para manejar tokens inválidos
        sin lanzar excepciones en endpoints que permiten acceso anónimo.
        """
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError):
            # Si el token es inválido, retornar None para permitir acceso anónimo
            # en endpoints que tienen permission_classes = [AllowAny]
            return None

    def get_user(self, validated_token):
        """
        Obtiene el usuario o empresa basándose en el token validado.
        """
        try:
            # Verificar si el token contiene company_id (empresa)
            if "company_id" in validated_token:
                company_id = validated_token["company_id"]
                try:
                    company = Company.objects.get(id=company_id)
                    if company.is_active:
                        return company
                except Company.DoesNotExist:
                    pass

            # Verificar si el token contiene user_id (investigador).
            # Identity usa "sub" como claim estándar y mantiene "user_id" por
            # compatibilidad con el frontend, así que aceptamos ambos.
            else:
                principal = principal_from_token(validated_token)
                if principal:
                    return principal

            # Si no se encuentra ni usuario ni empresa, devolver usuario anónimo
            return AnonymousUser()

        except (KeyError, ValueError):
            # Si hay algún error en el formato del token
            return AnonymousUser()
