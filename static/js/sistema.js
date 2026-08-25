document.addEventListener("DOMContentLoaded", () => {
    const botao = document.querySelector(".mobile-menu-button");
    const fundo = document.querySelector(".sidebar-backdrop");
    const fechar = () => {
        document.body.classList.remove("menu-open");
        botao?.setAttribute("aria-expanded", "false");
    };
    botao?.addEventListener("click", () => {
        const aberto = document.body.classList.toggle("menu-open");
        botao.setAttribute("aria-expanded", String(aberto));
    });
    fundo?.addEventListener("click", fechar);
    document.querySelectorAll(".sidebar-nav a").forEach(link => link.addEventListener("click", fechar));
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") fechar();
    });
});
