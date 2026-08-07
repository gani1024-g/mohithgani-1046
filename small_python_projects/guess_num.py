
import random
while True:
    num=random.randint(1, 1000)
    attempts=0
    print("Welcome to the Number Guessing Game!")
    print("I have selected a number between 1 and 1000. Try to guess it!")
    while True:
        guss = int(input("Enter your guess: "))
        attempts += 1
        if guss < num:
            print("Too low! Try again.")
        elif guss > num:
            print("Too high! Try again.")
        else:
            print(f"Congratulations! You guessed the number {num} in {attempts} attempts.")
            break

        score = 1000 - attempts * 10
        print(f"Your current score is: {score}")

    play_again = input("Play again? (y/n): ").strip().lower()
    if play_again != 'y' and play_again != 'yes':
        print("Thanks for playing!")
        break