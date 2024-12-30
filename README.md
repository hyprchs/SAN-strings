# SAN Strings

This simple script generates all **29,274** possible [Standard Algebraic Notation (SAN)](https://en.wikipedia.org/wiki/Algebraic_notation_(chess)#:~:text=Algebraic%20notation%20(or%20AN)%20is,books%2C%20magazines%2C%20and%20newspapers.) 
strings for chess moves, with logic to avoid listing SAN strings that can never actually occur for geometric reasons.

If someone notices missing strings, or strings which are generated but can never occur, please open an issue!*

###### * But after the last update, I truly think I got them all!

### Note
Check (`+`) and checkmate (`#`) symbols are omitted in `san_strings.txt` but included in `san_strings_with_symbols.txt`. It is fairly easy 
to convince yourself that no special logic is required to determine which subset of all SAN moves could deliver check/mate: all moves can 
deliver either check or checkmate at least via a discovery. Therefore, `san_strings_with_symbols.txt` (29,274 lines) is exactly three times the 
length of `san_strings.txt` (9,758 lines) as it simply makes two additional copies of each SAN move, one appending `+` and one appending `#`.
SANs in both files are sorted by the key `(len(san), san)`.

# Run it yourself
```sh
git clone https://github.com/jacksonthall22/SAN-strings.git && cd SAN-strings
pip install -r requirements.txt
python gen_san_strings.py
```

# How it works
## What are discriminators?
Generating every possible SAN move in chess would be simple if not for discriminators, which occasionally
must be inserted into the "standard" SAN move to disambiguate between multiple legal options.
 - N**b**d2:

   ![image](https://backscattering.de/web-boardimage/board.svg?size=200&coordinates=true&fen=8/8/8/8/8/5N2/8/1N6&arrows=Gb1d2)
 - R**5**e2:

   ![image](https://backscattering.de/web-boardimage/board.svg?size=200&coordinates=true&fen=8/8/8/4R3/8/8/8/4R3&arrows=Ge5e2)
 - Q**b6**e3:

   ![image](https://backscattering.de/web-boardimage/board.svg?size=200&coordinates=true&fen=8/8/1Q5Q/8/8/1Q6/8/8&arrows=Gb6e3)

If we have a `piece`, a `from_square`, and a `to_square`, how do we decide which (if any) discriminators
the SAN move might require? I'm glad you asked—this repo has the answer.

## SAN generation algorithms
In a previous version of this code, special logic was used to manually handle all the edge cases
for the different piece types. Unfortunately, this failed miserably, generating some syntactically-legal
SAN moves that could never actually occur and failing to generate some that could. When I dug into the issues
more deeply, I realized this problem is quite difficult to reason through.

Now, the code uses three much more logical and generalized algorithms that were designed to resemble how a human 
might decide whether a particular `from_square` -> `to_square` move by a certain `piece` type could
require a rank, file, and/or full-square discriminator respectively, based on which other squares a piece of
the same type could come from when moving to `to_square`. Read on for the pseudocode, as well as some more
intuitive explanations.

Note that only knight, bishop, rook, and queen moves ever use discriminators. Pawns have their own special 
move syntax and there is never more than one king per color. The details about how SAN strings are generated
for these piece types is omitted below because it is straightforward and comparatively uninteresting. However,
you can find the implementations in `gen_san_strings.py` at `get_pawn_sans()` and `get_king_sans()`.

### Pseudocode
#### File discriminators
- Given `piece` (must be a `N`, `B`, `R`, or `Q`)
- For each `to_square` in the board:
  - Initialize an empty board `b`
  - Place a `piece` on `b` at `to_square`
  - Get the `attacks` bitboard for `to_square`, a 64-bit binary number representing squares the `piece` could move to
  - For each `from_square` in `attacks`:
    - Define a bitboard `ray` whose truthy bits start at `to_square` and extend toward `from_square`, continuing past it until reaching a board edge
    - Remove all truthy bits in `ray` from `attacks`
    - Remove all truthy bits on the same file as `from_square` from `attacks`
    - If any file in `attacks` has any truthy bit, this move can require a file discriminator

#### Rank discriminators
- Given `piece` (must be a `N`, `B`, `R`, or `Q`)
- For each `to_square` in the board:
    - Initialize an empty board `b`
    - Place a `piece` on `b` at `to_square`
    - Get the `attacks` bitboard for `to_square`, a 64-bit binary number representing squares the `piece` could move to
    - For each `from_square` in `attacks`:
      - Define a bitboard `ray` whose truthy bits start at `to_square` and move toward `from_square`, continuing past it until reaching a board edge
      - Remove all truthy bits in `ray` from `attacks`
      - Remove all truthy bits **not** on the same file as `from_square` from `attacks`
      - If any rank in `attacks` has any truthy bit, this move can require a rank discriminator

#### Full-square discriminators
- Given `piece` (must be a `N`, `B`, `R`, or `Q`)
- For each `to_square` in the board:
  - Initialize an empty board `b`
  - Place a `piece` on `b` at `to_square`
  - Get the `attacks` bitboard for `to_square` a 64-bit binary number representing squares the `piece` could move to
  - For each `from_square` in `attacks`:
    - Define a bitboard `ray` whose truthy bits start at `to_square` and move toward `from_square`, continuing past it until reaching a board edge
    - Remove all truthy bits in `ray` from `attacks`
    - If there is any truthy bit in `from_square`'s rank and also in `from_square`'s file, this move can require a full-square discriminator

### Intuitive explanations
To really understand the code in this repo, we need to understand the algorithm a human uses
to determine whether a move from a `from_square` to a `to_square` might require a file, rank,
and/or full-square discriminator.

First we should consider that if moving from `from_square` to `to_square` is a legal
move, then even if there is another piece of the same type and color on the ray which extends 
from `to_square` to `from_square` and continues on to an edge of the board, moving that piece 
to `to_square` would be illegal. If this piece falls between `from_square` and `to_square`,
then the original move would not be legal, so we have a contradiction. If it is past 
`from_square` (on the extension of the ray between the squares that continues to the edge of 
the board), then it is not legal because it cannot jump over the piece at `from_square` to 
reach `to_square`.

This is important when considering disriminators because we are only interested in squares
from which another `piece` can legally move to `to_square`, and those which might create
a situation where a rank, file, or full-square discriminator is necessary.

#### File discriminators
With this in mind, the algorithm for determining whether we need a **file** discriminator
is as follows:
- Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
  of all the squares it can move to. These may all be considered possible `from_square`s.
- Consider each `from_square` in `attacks`:
    - Assume the move from `from_square` to `to_square` is legal. Then we know that 
      no other `piece` on the ray from `to_square` to `from_square` is relevant because
      its move to `to_square` would be illegal. Therefore, we can subtract the bitmask 
      of that ray from `attacks` for the next step, creating a bitboard representing all
      the other possible locations of a `piece` that could legally move to `to_square` 
      given that a `piece` can legally move from `from_square` to `to_square`.
    - We also know that any squares in this bitmask which fall on the same file as
      `from_square` are not relevant for determining whether a file discriminator might be 
      required: if another `piece` were to occupy one of those squares, then its move to
      `to_square` would necessarily require a rank discriminator, not a file discriminator.
      Therefore we subtract the bitmask of all squares in `from_square`'s file from the 
      bitboard in the previous step as well.
    - We now have a bitboard of all squares from which a `piece` can legally move to 
      `to_square` (given that the move `piece` from `from_square` to `to_square` is legal)
      such that, if a `piece` really were to occupy any one of those squares, it has 
      potential to create a situation where a file discriminator is necessary. All that
      is left to do is check whether one or more files in this bitboard have any truthy bits.
      If so, then the `from_square` for this iteration can require a file discriminator.

#### Rank discriminators
The algorithm for determining whether we need a **rank** discriminator is similar, but
has some differences which account for the fact that a file discriminator is preferred
over a rank discriminator when both can disambiguate the move:
- Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
  of all the squares it can move to. These may all be considered possible `from_square`s.
- Consider each `from_square` in `attacks`:
    - Subtract the extended ray from `to_square` towards `from_square` from `attacks`
      by the same logic as above.
    - This time, we know that any squares that **do not** fall on the same file as 
      `from_square` are not relevant for determining whether a rank discriminator might be 
      required: if another `piece` were to occupy one of those squares, then its move to
      `to_square` would necessarily preference the file discriminator, not the rank discriminator.
      Therefore we use a logical AND between the bitboard from the previous step and the
      bitmask of all squares in `from_square`'s file.
    - By the same logic as above, all that is left to do is check whether one or more ranks
      in this bitboard have any truthy bits. If so, then the `from_square` for this 
      iteration can require a rank discriminator.

#### Full-square discriminator
Determining whether we need a **full-square** discriminator is actually the simplest:
- Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
  of all the squares it can move to. These may all be considered possible `from_square`s.
- Consider each `from_square` in `attacks`:
    - Subtract the extended ray from `to_square` towards `from_square` from `attacks`
      by the same logic as above.
    - A full-square discriminator is required when there is another `piece` on `from_square`'s
      same file and another one on its same rank that can both move to `to_square`. Therefore,
      can use a logical AND between `attacks` and the bitmask of all squares in `from_square`'s
      file, then do the same for its rank, and if both of these have truthy bits, then the
      `from_square` for this iteration can require a full-square discriminator.
