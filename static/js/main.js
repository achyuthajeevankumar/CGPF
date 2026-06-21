/**
 * CALVARY GOSPEL PRAYER FELLOWSHIP - Core Client Logic
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Mobile Navigation Toggle
    const hamburger = document.querySelector(".hamburger");
    const navLinks = document.querySelector(".nav-links");

    if (hamburger && navLinks) {
        hamburger.addEventListener("click", () => {
            hamburger.classList.toggle("active");
            navLinks.classList.toggle("active");
        });

        // Close menu when a link is clicked
        navLinks.querySelectorAll("a").forEach(link => {
            link.addEventListener("click", () => {
                hamburger.classList.remove("active");
                navLinks.classList.remove("active");
            });
        });
    }

    // 2. Flash Messages Auto-dismiss
    const flashMessages = document.querySelectorAll(".flash-message");
    flashMessages.forEach(msg => {
        // Automatically hide toast messages after 5 seconds
        setTimeout(() => {
            msg.style.opacity = "0";
            msg.style.transform = "translateX(100%)";
            msg.style.transition = "all 0.5s ease";
            setTimeout(() => {
                msg.remove();
            }, 500);
        }, 5000);
    });

    // 3. Tab Navigation for Dashboards (Admin / User)
    const tabButtons = document.querySelectorAll("[data-tab-target]");
    const tabContents = document.querySelectorAll(".dashboard-tab-content");

    if (tabButtons.length > 0) {
        // Read active tab from hash or default to first
        const hash = window.location.hash;
        let activeTabName = hash ? hash.replace("#", "") : null;
        
        const activateTab = (tabName) => {
            let found = false;
            tabButtons.forEach(btn => {
                const target = btn.getAttribute("data-tab-target");
                if (target === tabName) {
                    btn.classList.add("active");
                    found = true;
                } else {
                    btn.classList.remove("active");
                }
            });

            tabContents.forEach(content => {
                const id = content.getAttribute("id");
                if (id === tabName) {
                    content.classList.add("active");
                } else {
                    content.classList.remove("active");
                }
            });

            // Fallback if no matching tab is found
            if (!found && tabButtons.length > 0) {
                const defaultTarget = tabButtons[0].getAttribute("data-tab-target");
                activateTab(defaultTarget);
            }
        };

        if (activeTabName) {
            activateTab(activeTabName);
        } else {
            const firstTarget = tabButtons[0].getAttribute("data-tab-target");
            activateTab(firstTarget);
        }

        tabButtons.forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const target = btn.getAttribute("data-tab-target");
                window.location.hash = target;
                activateTab(target);
            });
        });
    }

    // 4. Modal Triggers
    const modalTriggers = document.querySelectorAll("[data-modal-open]");
    modalTriggers.forEach(trigger => {
        trigger.addEventListener("click", (e) => {
            e.preventDefault();
            const modalId = trigger.getAttribute("data-modal-open");
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.style.display = "flex";
            }
        });
    });

    const modalCloses = document.querySelectorAll(".modal-close, .modal-backdrop");
    modalCloses.forEach(close => {
        close.addEventListener("click", () => {
            const modal = close.closest(".modal");
            if (modal) {
                modal.style.display = "none";
            }
        });
    });

    // Close modal on ESC key
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal").forEach(modal => {
                modal.style.display = "none";
            });
        }
    });

    // 5. Media Upload Client-Side Validations
    const uploadForm = document.querySelector("#upload-media-form");
    if (uploadForm) {
        const fileInput = uploadForm.querySelector("input[type='file']");
        
        uploadForm.addEventListener("submit", (e) => {
            if (fileInput && fileInput.files.length > 0) {
                const file = fileInput.files[0];
                const sizeLimitImg = 5 * 1024 * 1024; // 5MB
                const sizeLimitVid = 50 * 1024 * 1024; // 50MB
                
                const fileType = file.type;
                const fileSize = file.size;

                if (fileType.startsWith("image/")) {
                    if (fileSize > sizeLimitImg) {
                        e.preventDefault();
                        showToast("Image size must be less than 5MB.", "error");
                    }
                } else if (fileType.startsWith("video/")) {
                    if (fileSize > sizeLimitVid) {
                        e.preventDefault();
                        showToast("Video size must be less than 50MB.", "error");
                    }
                } else {
                    e.preventDefault();
                    showToast("Only image and video uploads are allowed.", "error");
                }
            }
        });
    }

    // Helper to generate dynamic toasts dynamically
    function showToast(message, type = "info") {
        let container = document.querySelector(".flash-container");
        if (!container) {
            container = document.createElement("div");
            container.className = "flash-container";
            document.body.appendChild(container);
        }

        const msgDiv = document.createElement("div");
        msgDiv.className = `flash-message flash-${type}`;
        msgDiv.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(msgDiv);

        setTimeout(() => {
            msgDiv.style.opacity = "0";
            msgDiv.style.transform = "translateX(100%)";
            msgDiv.style.transition = "all 0.5s ease";
            setTimeout(() => {
                msgDiv.remove();
            }, 500);
        }, 4000);
    }
});
