from django.core.management.base import BaseCommand, CommandError
import simplejson
from palmaimport import models
from palmaimport import serializers


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        for p in models.PHPPoule.objects.all():
            phase = models.TransientPhase(p, 1, 1, 38, 'Saison', 'FULLSEASON')
            print(simplejson.dumps(serializers.PhaseRankingSerializer(phase, context={'score_field': 'score'}).data))

        for j in models.PHPJoueur.objects.exclude(score__lte=0, score2__lte=0):
            print(simplejson.dumps(
                serializers.PlayerSerializer(j, context={'phases': [(1, 'score'), (3, 'score2')]}).data))

        for t in models.PHPTransfert.objects.select_related('joueur__club').select_related('ekyp').all():
            print(simplejson.dumps(serializers.SigningSerializer(t).data))

        # for e in models.PHPEkyp.objects.all():
        #     print(simplejson.dumps(serializers.TeamRankingSerializer(e, context={'score_field': 'score'}).data))
        #     # print(e.nom)
        # formation = simplejson.dumps(serializers.FormationSerializer(e.get_formation()).data)
        # print('formation %s' % formation)
        # composition = simplejson.dumps(serializers.CompositionSerializer(e.get_composition('score')).data)
        # print('composition %s' % composition)
        # for tr in e.phptransfert_set.select_related('joueur__club').all():
        #     pass
