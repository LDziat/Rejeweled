import uuid
import random
from django.db import models

GEM_TYPES = ["red", "blue", "green", "yellow", "purple", "orange", "white"]

class GameBoard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board_state = models.JSONField(default=list)  # Empty list by default
    last_updated = models.DateTimeField(auto_now=True)

    def generate_board(self):
        """Generates a new 8x8 board filled with random gems."""
        return [[random.choice(GEM_TYPES) for _ in range(8)] for _ in range(8)]

    def save(self, *args, **kwargs):
        """Ensure board_state is initialized when creating a new GameBoard instance."""
        if not self.board_state:
            self.board_state = self.generate_board()
        super().save(*args, **kwargs)

    def update_board(self, new_state):
        """Updates the board with a new state and saves it."""
        self.board_state = new_state
        self.save()
