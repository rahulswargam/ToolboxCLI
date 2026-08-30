"""2D grid navigation — pure logic, no Textual imports.

Kept deliberately framework-free so the whole movement model can be tested
exhaustively without spinning up a terminal or an app instance.

Model: rows are categories, columns are tools within that category. Rows are
ragged (categories have different tool counts), so vertical movement clamps
to the last available column of the target row.
"""

from __future__ import annotations


class GridNavigator:
    def __init__(self, row_lengths: list[int], row: int = 0, col: int = 0):
        if not row_lengths or any(n <= 0 for n in row_lengths):
            raise ValueError("every row must have at least one item")
        self.row_lengths = row_lengths
        self.row = row
        self.col = col

    @property
    def position(self) -> tuple[int, int]:
        return (self.row, self.col)

    def _clamp(self) -> None:
        self.row = max(0, min(self.row, len(self.row_lengths) - 1))
        self.col = max(0, min(self.col, self.row_lengths[self.row] - 1))

    def move(self, direction: str) -> tuple[int, int]:
        """Move and return the new (row, col).

        Horizontal movement wraps within the row — cycling through the tools
        of a category, per the 'cycle through tool buttons' requirement.
        Vertical movement wraps between rows and clamps the column so a long
        row never strands the cursor past the end of a shorter one.
        """
        if direction == "left":
            width = self.row_lengths[self.row]
            self.col = (self.col - 1) % width
        elif direction == "right":
            width = self.row_lengths[self.row]
            self.col = (self.col + 1) % width
        elif direction == "up":
            self.row = (self.row - 1) % len(self.row_lengths)
            self.col = min(self.col, self.row_lengths[self.row] - 1)
        elif direction == "down":
            self.row = (self.row + 1) % len(self.row_lengths)
            self.col = min(self.col, self.row_lengths[self.row] - 1)
        elif direction == "home":
            self.row, self.col = 0, 0
        elif direction == "end":
            self.row = len(self.row_lengths) - 1
            self.col = self.row_lengths[self.row] - 1
        self._clamp()
        return self.position

    def flat_index(self) -> int:
        """Position as a single index across all rows (row-major)."""
        return sum(self.row_lengths[:self.row]) + self.col

    def set_flat_index(self, index: int) -> tuple[int, int]:
        total = sum(self.row_lengths)
        index = max(0, min(index, total - 1))
        remaining = index
        for r, length in enumerate(self.row_lengths):
            if remaining < length:
                self.row, self.col = r, remaining
                return self.position
            remaining -= length
        return self.position
