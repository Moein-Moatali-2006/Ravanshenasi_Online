document.querySelectorAll(".password-toggle").forEach((toggle) => {
    toggle.addEventListener("click", () => {
        const input = toggle.parentElement.querySelector("input");
        const isVisible = input.type === "text";

        input.type = isVisible ? "password" : "text";
        toggle.setAttribute("aria-pressed", String(!isVisible));
        toggle.setAttribute(
            "aria-label",
            isVisible ? "نمایش رمز عبور" : "پنهان کردن رمز عبور"
        );
        toggle.querySelector("i").className = isVisible
            ? "bi bi-eye"
            : "bi bi-eye-slash";
    });
});
