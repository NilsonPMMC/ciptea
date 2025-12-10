from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from cadastro.views import BeneficiarioViewSet, SolicitacaoViewSet, DocumentoViewSet, gerar_carteira_pdf
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Router cria as URLs automaticamente (/api/beneficiarios/, /api/solicitacoes/)
router = DefaultRouter()
router.register(r'beneficiarios', BeneficiarioViewSet)
router.register(r'solicitacoes', SolicitacaoViewSet)
router.register(r'documentos', DocumentoViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/carteira/pdf/<str:protocolo>/', gerar_carteira_pdf, name='gerar_carteira_pdf'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# Necessário para servir as fotos (media) durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)