from django.db import models


class PHPClub(models.Model):
    nom = models.CharField(max_length=50)
    # uuid = models.CharField(max_length=50, null=True)
    id_lequipe = models.CharField(max_length=50, null=True)

    def __str__(self):
        return '%s' % self.nom

    @property
    def club_id(self):
        if self.id_lequipe != '':
            return int(self.id_lequipe)
        return None

    class Meta:
        db_table = 'club'


class PHPJoueur(models.Model):
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50, null=True)
    poste = models.CharField(max_length=1)
    # uuid = models.CharField(max_length=50, null=True)
    club = models.ForeignKey(PHPClub, on_delete=models.PROTECT, db_column='club_id')
    score = models.FloatField()
    score1 = models.FloatField()
    score2 = models.FloatField()

    def __str__(self):
        if self.prenom:
            return '%s %s' % (self.prenom, self.nom)
        else:
            return '%s' % self.nom

    @property
    def nb_notes(self):
        return self.phpprestation_set.filter(minutes__gte=30).exclude(note_lequipe__isnull=True,
                                                                      note_ff__isnull=True,
                                                                      note_sp__isnull=True,
                                                                      note_e__isnull=True,
                                                                      note_d__isnull=True
                                                                      ).count()

    class Meta:
        db_table = 'joueur'


class PHPTactique(models.Model):
    nb_g = models.IntegerField()
    nb_d = models.IntegerField()
    nb_m = models.IntegerField()
    nb_a = models.IntegerField()

    class Meta:
        db_table = 'tactique'


class TransientFormation:
    def __init__(self, g, d, m, a):
        self.G = g
        self.D = d
        self.M = m
        self.A = a


class TransientComposition:
    def __init__(self):
        self.G = list()
        self.D = list()
        self.M = list()
        self.A = list()


class PHPPoule(models.Model):
    nom = models.CharField(max_length=50)

    class Meta:
        db_table = 'poule'


class PHPEkyp(models.Model):
    nom = models.CharField(max_length=50)
    score = models.FloatField()
    score1 = models.FloatField()
    score2 = models.FloatField()
    tactique = models.ForeignKey(PHPTactique, on_delete=models.PROTECT, db_column='tactique_id')
    poule = models.ForeignKey(PHPPoule, on_delete=models.PROTECT, db_column='poule_id')
    complete = models.BooleanField()

    def get_formation(self):
        tac = self.tactique
        return TransientFormation(tac.nb_g, tac.nb_d, tac.nb_m, tac.nb_a)

    def get_composition(self, score_field):
        compo = TransientComposition()
        formation = self.get_formation()
        for poste in ['G', 'D', 'M', 'A']:
            limit = formation.__getattribute__(poste)
            for jo in self.phptransfert_set.select_related('joueur').filter(joueur__poste=poste).annotate(
                    real_score=models.F('joueur__%s' % score_field) * models.F('coeff_bonus_achat')).order_by(
                    '-real_score')[:limit]:
                compo.__getattribute__(poste).append(jo)
        return compo

    def __str__(self):
        return self.nom

    class Meta:
        db_table = 'ekyp'


class PHPTransfert(models.Model):
    joueur = models.OneToOneField(PHPJoueur, on_delete=models.PROTECT, db_column='joueur_id', primary_key=True)
    ekyp = models.ForeignKey(PHPEkyp, on_delete=models.PROTECT, db_column='ekyp_id')
    transfert_date = models.DateField()
    coeff_bonus_achat = models.FloatField()
    prix_achat = models.FloatField()
    choix_draft = models.IntegerField()
    poule_id = models.IntegerField()

    class Meta:
        db_table = 'transfert'
        unique_together = (('joueur', 'poule_id'),)


class TransientPhase:
    def __init__(self, poule, id, journee_first, journee_last, name, type):
        self.poule = poule
        self.id = id
        self.journee_first = journee_first
        self.journee_last = journee_last
        self.name = name
        self.type = type


class PHPPrestation(models.Model):
    joueur = models.ForeignKey(PHPJoueur, on_delete=models.PROTECT, db_column='joueur_id')
    minutes = models.IntegerField()
    note_lequipe = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    note_ff = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    note_sp = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    note_d = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    note_e = models.DecimalField(max_digits=3, decimal_places=1, null=True)

    class Meta:
        db_table = 'prestation'
