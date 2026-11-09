from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class NutzerManager(BaseUserManager):
    """Nutzer werden über die E-Mail-Adresse identifiziert, nicht über einen Benutzernamen."""

    use_in_migrations = True

    def _anlegen(self, email, password, **felder):
        if not email:
            raise ValueError("Eine E-Mail-Adresse ist erforderlich.")
        nutzer = self.model(email=self.normalize_email(email), **felder)
        nutzer.set_password(password)
        nutzer.save(using=self._db)
        return nutzer

    def create_user(self, email, password=None, **felder):
        felder.setdefault("is_staff", False)
        felder.setdefault("is_superuser", False)
        return self._anlegen(email, password, **felder)

    def create_superuser(self, email, password=None, **felder):
        felder.setdefault("is_staff", True)
        felder.setdefault("is_superuser", True)
        if felder["is_staff"] is not True or felder["is_superuser"] is not True:
            raise ValueError("Ein Superuser braucht is_staff=True und is_superuser=True.")
        return self._anlegen(email, password, **felder)


class Nutzer(AbstractUser):
    username = None
    email = models.EmailField("E-Mail-Adresse", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = NutzerManager()

    class Meta:
        verbose_name = "Nutzer"
        verbose_name_plural = "Nutzer"
        ordering = ["email"]

    def __str__(self):
        return self.email
