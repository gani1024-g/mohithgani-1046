import random
num=random.randint(1, 1000)
attempts=0
print("Welcome to the Number Guessing Game!")
print("I have selected a number between 1 and 1000. Try to guess it!")
while True:
    guss=int(input("Enter your guess: "))
    attempts+=1
    if guss<num:
        print("Too low! Try again.")
    elif guss>num:
        print("Too high! Try again.")
    else:
        print(f"Congratulations! You guessed the number {num} in {attempts} attempts.")
        break
    score=1000-attempts*10
    