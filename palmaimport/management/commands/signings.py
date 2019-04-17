from django.core.management.base import BaseCommand, CommandError
from palmaimport import models


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        for t in models.PHPTransfert.objects.select_related('joueur__club').select_related('ekyp').all():
            print('%s %s' % (t.joueur.nom, t.prix_achat))
