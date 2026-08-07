import random
while True:
    print("Welcome to Rock, Paper, Scissors!")
    print("1. Rock")
    print("2. Paper")
    print("3. Scissors")
    user_input = input("Enter your choice (1-3) or 'q' to quit: ")
    
    if user_input.lower() == 'q':
        print("Thanks for playing!")
        break
    
    try:
        user = int(user_input)
        if user < 1 or user > 3:
            print("Invalid choice. Please choose a number between 1 and 3.")
            continue
    except ValueError:
        print("Invalid input. Please enter a number between 1 and 3 or 'q' to quit.")
        continue

    choices = ['rock', 'paper', 'scissors']
    comp = random.choice(choices)
    print(f"Computer chose: {comp}")
    
    if (user == 1 and comp == 'rock') or (user == 2 and comp == 'paper') or (user == 3 and comp == 'scissors'):
        print("It's a tie!")
    elif (user == 1 and comp == 'scissors') or (user == 2 and comp == 'rock') or (user == 3 and comp == 'paper'):
        print("You win!")
    else:
        print("Computer wins!")