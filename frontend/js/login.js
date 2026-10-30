const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const loginError = document.getElementById("login-error");
const signinTab = document.getElementById("signin-tab");
const signupTab = document.getElementById("signup-tab");
const authTitle = document.getElementById("auth-title");
const authDescription = document.getElementById("auth-description");
const authEyebrow = document.getElementById("auth-eyebrow");
const authFootnote = document.getElementById("auth-footnote");

if (localStorage.getItem("campuscore_token")) {
  window.location.replace("/");
}

function setMode(mode) {
  const isSignup = mode === "signup";
  loginForm.hidden = isSignup;
  signupForm.hidden = !isSignup;
  signinTab.classList.toggle("active", !isSignup);
  signupTab.classList.toggle("active", isSignup);
  signinTab.setAttribute("aria-selected", String(!isSignup));
  signupTab.setAttribute("aria-selected", String(isSignup));
  authEyebrow.textContent = isSignup ? "JOIN YOUR CAMPUS" : "STUDENT ADMINISTRATION";
  authTitle.textContent = isSignup ? "Create your account" : "Welcome back";
  authDescription.textContent = isSignup
    ? "Set up your administrator account and start bringing campus life together."
    : "Sign in to manage your campus, students and academic records.";
  authFootnote.textContent = isSignup
    ? "Your account gives you administrator access to this campus."
    : "Secure access for campus administrators.";
  loginError.hidden = true;
}

signinTab.addEventListener("click", () => setMode("signin"));
signupTab.addEventListener("click", () => setMode("signup"));

async function submitAuthForm(form, endpoint, loadingText, buttonText, onSuccess) {
  loginError.hidden = true;
  const button = form.querySelector("button");
  button.disabled = true;
  button.querySelector("span").textContent = loadingText;
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Unable to complete your request.");
    localStorage.setItem("campuscore_token", body.token);
    localStorage.setItem("campuscore_user", JSON.stringify(body.user));
    onSuccess();
  } catch (error) {
    loginError.textContent = error.message || "Unable to reach the server. Please try again.";
    loginError.hidden = false;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = buttonText;
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitAuthForm(
    loginForm,
    "/api/auth/login",
    "Signing in…",
    "Sign in to dashboard",
    () => window.location.replace("/"),
  );
});

signupForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const password = signupForm.elements.password.value;
  const confirmation = signupForm.elements.confirm_password.value;
  if (password !== confirmation) {
    loginError.textContent = "Passwords do not match.";
    loginError.hidden = false;
    return;
  }
  submitAuthForm(
    signupForm,
    "/api/auth/register",
    "Creating account…",
    "Create administrator account",
    () => window.location.replace("/"),
  );
});
