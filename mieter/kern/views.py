from django.views.generic import TemplateView


class StartseiteView(TemplateView):
    template_name = "kern/startseite.html"
