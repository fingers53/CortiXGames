// Function to generate a random 5-digit username as placeholder
function setRandomPlaceholder() {
    const usernameInput = document.getElementById("username");
    const randomNum = Math.floor(10000 + Math.random() * 90000);
    usernameInput.placeholder = `user_${randomNum}`;
}

// Function to confirm and save the username
function confirmUsername() {
    const usernameInput = document.getElementById("username");
    const enterButton = document.getElementById("enter-button");
    const username = usernameInput.value.trim() || usernameInput.placeholder;

    // Check if username is already in use
    const usernames = JSON.parse(localStorage.getItem("usernames")) || [];
    if (usernames.includes(username)) {
        alert("Username is already taken. Please choose another one.");
        return;
    }

    // Save the username in localStorage
    usernames.push(username);
    localStorage.setItem("usernames", JSON.stringify(usernames));
    localStorage.setItem("username", username);  // Save for this user's session

    // Style changes after confirmation
    usernameInput.value = username;
    usernameInput.disabled = true;
    usernameInput.style.backgroundColor = "#f0f0f0";
    usernameInput.style.color = "#555";
    enterButton.style.display = "none";
}

// Set random placeholder on page load
window.onload = function () {
    setRandomPlaceholder();

    // If a username is already set in localStorage, disable the input
    const savedUsername = localStorage.getItem("username");
    if (savedUsername) {
        const usernameInput = document.getElementById("username");
        usernameInput.value = savedUsername;
        usernameInput.disabled = true;
        usernameInput.style.backgroundColor = "#f0f0f0";
        usernameInput.style.color = "#555";
        document.getElementById("enter-button").style.display = "none";
    }
};
