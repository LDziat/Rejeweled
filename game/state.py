import random
import time

class BejeweledGame:
    def __init__(self, rows=8, cols=8):
        self.rows = rows
        self.cols = cols
        self.board = self.generate_board()

    def generate_board(self):
        """Generates a new game board with random gems."""
        gem_colors = ["red", "blue", "green", "yellow", "purple", "orange", "white"]
        return [
            [random.choice(gem_colors) for _ in range(self.cols)]
            for _ in range(self.rows)
        ]
    
    def apply_gravity(self):
        """Make gems fall down and fill empty spaces, properly shifting all columns."""
        for x in range(len(self.board[0])):  # Iterate over columns
            column = [self.board[y][x] for y in range(len(self.board))]  # Extract column
            column = [gem for gem in column if gem != ""]  # Remove empty spaces
            empty_slots = len(self.board) - len(column)  # Count empty spaces

            # Fill from top with new gems
            new_gems = [random.choice(["red", "blue", "green", "yellow", "purple", "orange", "white"])
                        for _ in range(empty_slots)]
            
            column = new_gems + column  # New gems come from the top

            # Write back to board
            for y in range(len(self.board)):
                self.board[y][x] = column[y]
        

    def swap(self, x1, y1, x2, y2):
        """Swap two gems and handle match clearing, cascading, and frame-by-frame animation."""
        self.board[int(y1)][int(x1)], self.board[int(y2)][int(x2)] = self.board[int(y2)][int(x2)], self.board[int(y1)][int(x1)]

        self.process_cascading()  # Start the cascading animation


    def check_for_matches(self):
        """Check for horizontal or vertical matches and clear them."""
        to_clear = set()

        # Ensure all checks compare exact string values
        for y in range(len(self.board)):
            for x in range(len(self.board[0]) - 2):
                if (self.board[y][x] == self.board[y][x+1] == self.board[y][x+2] 
                    and isinstance(self.board[y][x], str) and self.board[y][x] != ""):
                    to_clear.update([(y, x), (y, x+1), (y, x+2)])

        for x in range(len(self.board[0])):
            for y in range(len(self.board) - 2):
                if (self.board[y][x] == self.board[y+1][x] == self.board[y+2][x] 
                    and isinstance(self.board[y][x], str) and self.board[y][x] != ""):
                    to_clear.update([(y, x), (y+1, x), (y+2, x)])

        # Clear matched gems
        for y, x in to_clear:
            self.board[y][x] = ""  # Mark cleared spots as empty

        return bool(to_clear)  # Return True if matches were found



    def process_cascading(self):
        """Recursively apply gravity, clear matches, and wait for animation."""
        while self.check_for_matches():  # Keep clearing matches until none exist
            self.apply_gravity()  # Move gems down
            time.sleep(0.5)  # Pause for animation effect

    def to_dict(self):
        """Returns the current board as a list of lists to send over WebSocket."""
        return self.board

    import random
