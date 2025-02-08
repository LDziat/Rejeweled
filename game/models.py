from django.db import models
from django.contrib.auth.models import User
import uuid
import random

GEM_TYPES = ["red", "blue", "green", "yellow", "purple", "orange", "white"]

class GameBoard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board_state = models.JSONField(default=list)
    last_updated = models.DateTimeField(auto_now=True)

    def generate_board(self):
        return [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]

    def save(self, *args, **kwargs):
        if not self.board_state:
            self.board_state = self.generate_board()
        super().save(*args, **kwargs)

class GamePlayer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)

    def update_score(self, points):
        self.score += points
        self.save()
