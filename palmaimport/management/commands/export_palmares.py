from django.core.management.base import BaseCommand, CommandError
import simplejson
from palmaimport import models
from palmaimport import serializers
from datetime import datetime
import argparse
import codecs


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        parser.add_argument('-l', '--league', help='League id dans la bdd NKCUP', required=True, type=int)
        parser.add_argument('-d', '--date', help='Date de fin de la saison, sert à trier les entrées de palmarès',
                            required=True, type=valid_date)
        parser.add_argument('-n', '--name', required=True, type=str)
        parser.add_argument('-s', '--slogan', required=True, type=str)

    def handle(self, *args, **options):
        poule = models.PHPPoule.objects.first()
        clausura = models.TransientPhase(poule, 3, 19, 38, 'Clausura 2016', 'HALFSEASON')
        clausura_ranking = serializers.PhaseRankingSerializer(clausura, context={'score_field': 'score2'}).data

        season = models.TransientPhase(poule, 1, 1, 38, 'Saison', 'FULLSEASON')
        season_ranking = serializers.PhaseRankingSerializer(season, context={'score_field': 'score'}).data

        apertura = models.TransientPhase(poule, 2, 1, 19, 'Apertura 2015', 'HALFSEASON')
        apertura_ranking = serializers.PhaseRankingSerializer(apertura, context={'score_field': 'score1',
                                                                                 'apertura_simulator': True}).data

        final_ranking_list = [season_ranking,
                              apertura_ranking,
                              clausura_ranking
                              ]

        players_ranking = serializers.PlayerSerializer(models.PHPJoueur.objects.exclude(score__lte=0, score2__lte=0),
                                                       many=True,
                                                       context={'phases': [(1, 'score'), (2, 'score1'), (3, 'score2')]}
                                                       ).data

        signings_history = serializers.SigningSerializer(
            models.PHPTransfert.objects.select_related('joueur__club').select_related('ekyp').all(),
            many=True
        ).data

        with codecs.open("%s.sql" % options['name'], "w", "utf-8") as f:
            f.write(
                "insert into game_palmares(league_instance_name, league_instance_slogan, league_instance_end, final_ranking, signings_history, players_ranking, league_id)"
                "values("
                "'%(name)s', "
                "'%(slogan)s', "
                "'%(end)s'::timestamptz, "
                "'%(ranking)s', "
                "'%(signings)s', "
                "'%(players)s', "
                "%(league)d"
                ");" % {
                    'name': options['name'],
                    'slogan': options.get('slogan', None),
                    'end': datetime.combine(options['date'],
                                            datetime.min.time()).isoformat(),
                    'ranking': simplejson.dumps(simplejson.dumps(final_ranking_list)).replace("'", "''"),
                    'players': simplejson.dumps(simplejson.dumps(players_ranking)).replace("'", "''"),
                    'signings': simplejson.dumps(simplejson.dumps(signings_history)).replace("'", "''"),
                    'league': options['league']
                }
            )
