function toggleTheme() {
    document.body.classList.toggle("dark-mode");

    if (document.body.classList.contains("dark-mode")) {
        localStorage.setItem("theme", "dark");
        document.getElementById("theme-toggle").innerText = "☀️ Light Mode";
    } else {
        localStorage.setItem("theme", "light");
        document.getElementById("theme-toggle").innerText = "🌙 Dark Mode";
    }
}

window.onload = () => {
    const theme = localStorage.getItem("theme");
    if (theme === "dark") {
        document.body.classList.add("dark-mode");
        document.getElementById("theme-toggle").innerText = "☀️ Light Mode";
    }
};
