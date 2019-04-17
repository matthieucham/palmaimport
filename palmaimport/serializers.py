from palmaimport import models
from django.db.models import F
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from rest_framework import serializers
import decimal
import codecs


class FormationSerializer(serializers.Serializer):
    G = serializers.IntegerField()
    D = serializers.IntegerField()
    M = serializers.IntegerField()
    A = serializers.IntegerField()


class ClubSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='club_id')
    name = serializers.CharField(source='nom')
    nom = serializers.CharField()

    class Meta:
        model = models.PHPClub
        fields = ('name', 'id', 'nom')


class JoueurSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return str(obj)

    class Meta:
        model = models.PHPJoueur
        fields = ('id', 'name')


class FakeCompoPlayer:
    def __init__(self, joueur=None, real_score=None, coeff_bonus_achat=None):
        self.joueur = joueur
        self.real_score = real_score
        self.coeff_bonus_achat = coeff_bonus_achat


class CompositionPlayerSerializer(serializers.Serializer):
    club = serializers.SerializerMethodField()
    player = JoueurSerializer(source='joueur', read_only=True)
    score = serializers.DecimalField(source='real_score', max_digits=7, decimal_places=3)
    score_factor = serializers.DecimalField(source='coeff_bonus_achat', max_digits=7, decimal_places=2)

    def get_club(self, obj):
        return ClubSerializer(obj.joueur.club).data


class CompositionSerializer(serializers.Serializer):
    A = CompositionPlayerSerializer(many=True, read_only=True)
    D = CompositionPlayerSerializer(many=True, read_only=True)
    G = CompositionPlayerSerializer(many=True, read_only=True)
    M = CompositionPlayerSerializer(many=True, read_only=True)


class TeamAttributesSerializer(serializers.Serializer):
    formation = serializers.SerializerMethodField()
    composition = serializers.SerializerMethodField()

    def get_formation(self, obj):
        return FormationSerializer(obj.get_formation(), read_only=True).data

    def get_composition(self, obj):
        return CompositionSerializer(obj.get_composition(self.context['score_field']), read_only=True).data


class EkypSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return str(obj)

    def get_id(self, obj):
        return 0

    class Meta:
        model = models.PHPEkyp
        fields = ('id', 'name')


class TeamRankingSerializer(serializers.Serializer):
    attributes = serializers.SerializerMethodField()
    is_complete = serializers.BooleanField(source='complete')
    score = serializers.SerializerMethodField()
    team = EkypSerializer(source='*', read_only=True)
    rank = serializers.SerializerMethodField()
    missing_notes = serializers.SerializerMethodField()

    def get_attributes(self, obj):
        return TeamAttributesSerializer(obj, read_only=True, context=self.context).data

    def get_rank(self, obj):
        return self.context['rank']

    def get_score(self, obj):
        score_field = self.context['score_field']
        val = obj.__getattribute__(score_field)
        return serializers.DecimalField(max_digits=7, decimal_places=3).to_representation(val)

    def get_missing_notes(self, obj):
        if self.context['score_field'] is 'score':
            composition = obj.get_composition(self.context['score_field'])
            target = 26
            count_missing = 0
            for p in ['G', 'D', 'M', 'A']:
                for j in composition.__getattribute__(p):
                    notes_j = j.joueur.nb_notes
                    if notes_j < target:
                        count_missing += (target - notes_j)
            return count_missing
        return None


class TeamRankingAperturaSerializer(serializers.Serializer):
    attributes = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    team = EkypSerializer(source='*', read_only=True)
    rank = serializers.SerializerMethodField()
    missing_notes = serializers.SerializerMethodField()

    def get_attributes(self, obj):
        with codecs.open('apertura%d' % self.context['rank'], 'r', 'utf-8') as f:
            team_name = f.readline()
            roster = f.readline()
            by_line = roster.split(' - ')
            nb_by_poste = dict()
            composition = models.TransientComposition()
            for p, i in [('G', 0), ('D', 1), ('M', 2), ('A', 3)]:
                nb_by_poste[p] = len(by_line[i].split(','))
                for rawname in by_line[i].split(','):
                    jname = rawname.strip()
                    prenom_nom = jname.split('.')
                    if len(prenom_nom) == 1:
                        nom = prenom_nom[0]
                        prenom = ''
                    else:
                        nom = prenom_nom[1]
                        prenom = prenom_nom[0]
                    try:
                        joueur = models.PHPJoueur.objects.filter(poste=p).get(nom__startswith=nom,
                                                                              prenom__startswith=prenom)
                    except models.PHPJoueur.DoesNotExist as e:
                        print(jname)
                        raise e
                    except MultipleObjectsReturned:
                        try:
                            joueur = models.PHPJoueur.objects.filter(poste=p).filter(
                                phptransfert__ekyp=self.context['ekyp']).get(nom__istartswith=nom,
                                                                             prenom__istartswith=prenom)
                        except models.PHPJoueur.DoesNotExist as e:
                            print('no transfer for ambiguous %s' % jname)
                            raise e
                    # il faut enregistrer le transfert qui correspond à ce joueur.
                    # S'il n'en a pas (libéré pour la 2e phase), on en fabrique un faux
                    try:
                        transfert = models.PHPTransfert.objects.filter(pk=joueur.phptransfert.pk).annotate(
                            real_score=F('joueur__%s' % self.context['score_field']) * F('coeff_bonus_achat')).first()
                    except ObjectDoesNotExist:
                        transfert = FakeCompoPlayer(joueur=joueur, coeff_bonus_achat=1.00,
                                                    real_score=joueur.__getattribute__(self.context['score_field']))
                    composition.__getattribute__(p).append(transfert)
            formation = models.TransientFormation(nb_by_poste['G'], nb_by_poste['D'], nb_by_poste['M'],
                                                  nb_by_poste['A'])
            return {'formation': FormationSerializer(formation, read_only=True).data,
                    'composition': CompositionSerializer(composition, read_only=True).data}

    def get_is_complete(self, obj):
        return True

    def get_rank(self, obj):
        return self.context['rank']

    def get_score(self, obj):
        val = self.context['score']
        return serializers.DecimalField(max_digits=7, decimal_places=3).to_representation(val)

    def get_missing_notes(self, obj):
        return None


class RankingDivisionSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='nom')
    level = serializers.SerializerMethodField()
    ranking = serializers.SerializerMethodField()

    def get_ranking(self, obj):
        if self.context.get('apertura_simulator', False):
            rank = self.simulate_ranking_apertura()
        else:
            rank = []
            rankek = 1
            for ek in obj.phpekyp_set.order_by('-complete').order_by('-%s' % self.context['score_field']):
                rank.append(
                    TeamRankingSerializer(ek,
                                          context={'score_field': self.context['score_field'], 'rank': rankek}).data)
                rankek += 1
        return rank

    def simulate_ranking_apertura(self):
        rank = []
        for i in range(1, 4):
            with codecs.open('apertura%d' % i, 'r', 'utf-8') as f:
                team_name = f.readline().strip()
                team = models.PHPEkyp.objects.get(nom__istartswith=team_name[:8])
                roster = f.readline()
                score = f.readline()
                rank.append(
                    TeamRankingAperturaSerializer(team,
                                                  context={'rank': i, 'score': float(score), 'ekyp': team,
                                                           'score_field': self.context['score_field']}).data)
        return rank

    def get_level(self, obj):
        return 1

    class Meta:
        model = models.PHPPoule
        fields = ('id', 'level', 'name', 'ranking')


class PhaseCurrentRankingSerializer(serializers.Serializer):
    league_instance_phase = serializers.IntegerField(source='id')
    number = serializers.IntegerField(source='journee_last')
    ranking_ekyps = serializers.SerializerMethodField()

    def get_ranking_ekyps(self, obj):
        return RankingDivisionSerializer([obj.poule], many=True, read_only=True, context=self.context).data


class PhaseRankingSerializer(serializers.Serializer):
    current_ranking = serializers.SerializerMethodField()
    id = serializers.IntegerField()
    journee_first = serializers.IntegerField()
    journee_last = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()

    def get_current_ranking(self, obj):
        return PhaseCurrentRankingSerializer(obj, read_only=True, context=self.context).data


class PlayerSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    poste = serializers.CharField()
    club = ClubSerializer(read_only=True)
    scores = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        return str(obj)

    def get_id(self, obj):
        return 0

    def get_scores(self, obj):
        return {phid: round(obj.__getattribute__(score_field), 1) for phid, score_field in self.context['phases']}

    class Meta:
        model = models.PHPJoueur
        fields = ('id', 'display_name', 'poste', 'club', 'scores')


class PlayerWithoutScoreSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    poste = serializers.CharField()
    club = ClubSerializer(read_only=True)

    def get_display_name(self, obj):
        return str(obj)

    def get_id(self, obj):
        return 0

    class Meta:
        model = models.PHPJoueur
        fields = ('id', 'display_name', 'poste', 'club')


class SigningAttributesSerializer(serializers.ModelSerializer):
    pick_order = serializers.IntegerField(source='choix_draft')
    amount = serializers.DecimalField(source='prix_achat', max_digits=4, decimal_places=1)
    type = serializers.SerializerMethodField()

    def get_type(self, obj):
        if obj.choix_draft > 0:
            return 'DRFT'
        else:
            return 'PA'

    class Meta:
        model = models.PHPTransfert
        fields = ('pick_order',
                  'amount',
                  'type')


class SigningSerializer(serializers.ModelSerializer):
    begin = serializers.DateField(source='transfert_date')
    end = serializers.SerializerMethodField()
    player = PlayerWithoutScoreSerializer(source='joueur', read_only=True)
    team = EkypSerializer(source='ekyp', read_only=True)
    attributes = SigningAttributesSerializer(source='*', read_only=True)

    def get_end(self, obj):
        return None

    class Meta:
        model = models.PHPTransfert
        fields = ('begin',
                  'end',
                  'player',
                  'team',
                  'attributes')
