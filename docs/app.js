
const canvas = document.getElementById("canvas");
const properties = document.getElementById("properties");

let components = [
    {
        type: "text",
        content: "Support Center"
    },
    {
        type: "text",
        content: "Select a category below to create a ticket."
    },
    {
        type: "dropdown",
        placeholder: "Choose a ticket category...",
        options: [
            {
                label: "General Support",
                value: "general",
                description: "General questions",
                emoji: "🎫",
                form: [
                    {
                        label: "Describe your issue",
                        style: "paragraph",
                        required: true
                    }
                ]
            },
            {
                label: "Purchase Support",
                value: "purchase",
                description: "Purchase-related questions",
                emoji: "🛒",
                form: [
                    {
                        label: "Order ID",
                        style: "short",
                        required: true
                    },
                    {
                        label: "Describe your issue",
                        style: "paragraph",
                        required: true
                    }
                ]
            }
        ]
    }
];

let selected = 0;

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function save() {
    localStorage.setItem(
        "ticketStudioComponents",
        JSON.stringify(components)
    );
}

function render() {
    canvas.innerHTML = `
        <div class="discord-preview" id="preview"></div>
    `;

    const preview = document.getElementById("preview");

    components.forEach((component, index) => {
        const element = document.createElement("div");

        element.className =
            "component-preview" +
            (selected === index ? " selected" : "");

        element.onclick = () => {
            selected = index;
            render();
        };

        let content = "";

        if (component.type === "text") {
            content = `
                <small>TEXT DISPLAY</small>
                <div>${escapeHTML(component.content)}</div>
            `;
        }

        if (component.type === "container") {
            content = `
                <small>CONTAINER</small>
                <div class="fake-dropdown">
                    ${escapeHTML(component.content)}
                </div>
            `;
        }

        if (component.type === "dropdown") {
            content = `
                <small>STRING SELECT MENU</small>
                <div class="fake-dropdown">
                    ${escapeHTML(component.placeholder)}
                    <span style="float:right">⌄</span>
                </div>
                <small>${component.options.length} options</small>
            `;
        }

        if (component.type === "button") {
            content = `
                <small>BUTTON</small>
                <span class="fake-button">
                    ${escapeHTML(component.label)}
                </span>
            `;
        }

        if (component.type === "separator") {
            content = `
                <small>SEPARATOR</small>
                <hr>
            `;
        }

        element.innerHTML = content;
        preview.appendChild(element);
    });

    renderProperties();
    save();
}

function renderProperties() {
    const component = components[selected];

    if (!component) {
        properties.innerHTML = "<p>Select a component.</p>";
        return;
    }

    let html = "";

    if (component.type === "text" ||
        component.type === "container") {

        html += `
            <label>Content</label>
            <textarea data-field="content">${escapeHTML(component.content)}</textarea>
        `;
    }

    if (component.type === "button") {
        html += `
            <label>Button label</label>
            <input data-field="label"
                value="${escapeHTML(component.label)}">
        `;
    }

    if (component.type === "dropdown") {
        html += `
            <label>Placeholder</label>
            <input data-field="placeholder"
                value="${escapeHTML(component.placeholder)}">

            <h4>Dropdown options</h4>
        `;

        component.options.forEach((option, index) => {
            html += `
                <div style="border:1px solid #292d3c;padding:10px;margin:10px 0;border-radius:8px">

                    <label>Option label</label>
                    <input data-option="${index}"
                        data-key="label"
                        value="${escapeHTML(option.label)}">

                    <label>Option value</label>
                    <input data-option="${index}"
                        data-key="value"
                        value="${escapeHTML(option.value)}">

                    <label>Description</label>
                    <input data-option="${index}"
                        data-key="description"
                        value="${escapeHTML(option.description)}">

                    <label>Emoji</label>
                    <input data-option="${index}"
                        data-key="emoji"
                        value="${escapeHTML(option.emoji)}">

                    <label>Form questions (one per line)</label>
                    <textarea data-form="${index}">${escapeHTML(
                        (option.form || []).map(q => q.label).join("\n")
                    )}</textarea>

                    <button data-remove="${index}">
                        Remove option
                    </button>
                </div>
            `;
        });

        html += `
            <button id="add-option">+ Add dropdown option</button>
        `;
    }

    html += `
        <button id="delete-component">
            Delete component
        </button>
    `;

    properties.innerHTML = html;

    properties.querySelectorAll("[data-field]").forEach(input => {
        input.addEventListener("input", () => {
            component[input.dataset.field] = input.value;
            render();
        });
    });

    properties.querySelectorAll("[data-option]").forEach(input => {
        input.addEventListener("input", () => {
            const option = component.options[Number(input.dataset.option)];
            option[input.dataset.key] = input.value;
            render();
        });
    });

    properties.querySelectorAll("[data-form]").forEach(input => {
        input.addEventListener("input", () => {
            const option = component.options[Number(input.dataset.form)];

            option.form = input.value
                .split("\n")
                .filter(q => q.trim())
                .map(q => ({
                    label: q.trim(),
                    style: q.length > 45 ? "paragraph" : "short",
                    required: true
                }));

            save();
        });
    });

    properties.querySelectorAll("[data-remove]").forEach(button => {
        button.onclick = () => {
            component.options.splice(
                Number(button.dataset.remove), 1
            );
            render();
        };
    });

    const addOption = document.getElementById("add-option");

    if (addOption) {
        addOption.onclick = () => {
            if (component.options.length >= 25) {
                alert("Discord allows up to 25 dropdown options.");
                return;
            }

            component.options.push({
                label: "New category",
                value: "category_" + Date.now(),
                description: "New ticket category",
                emoji: "🎫",
                form: []
            });

            render();
        };
    }

    document.getElementById("delete-component").onclick = () => {
        components.splice(selected, 1);
        selected = Math.max(0, selected - 1);
        render();
    };
}


// ADD COMPONENTS

document.querySelectorAll("[data-add]").forEach(button => {

    button.onclick = () => {

        const type = button.dataset.add;

        let component;

        if (type === "text") {
            component = {
                type: "text",
                content: "New text"
            };
        }

        if (type === "container") {
            component = {
                type: "container",
                content: "Container content"
            };
        }

        if (type === "dropdown") {
            component = {
                type: "dropdown",
                placeholder: "Choose an option...",
                options: []
            };
        }

        if (type === "button") {
            component = {
                type: "button",
                label: "Open ticket"
            };
        }

        if (type === "separator") {
            component = {
                type: "separator"
            };
        }

        components.push(component);
        selected = components.length - 1;

        render();
    };
});


// EXPORT PANEL CONFIGURATION

document.getElementById("export").onclick = () => {

    const dropdown = components.find(
        component => component.type === "dropdown"
    );

    const textComponents = components.filter(
        component => component.type === "text"
    );

    const config = {
        title: textComponents[0]?.content || "Support Center",

        description: textComponents
            .slice(1)
            .map(component => component.content)
            .join("\n"),

        accent: "#806dff",

        placeholder: dropdown?.placeholder ||
            "Choose a ticket category...",

        categories: dropdown?.options || []
    };

    const blob = new Blob(
        [JSON.stringify(config, null, 4)],
        { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "ticket-panel.json";
    link.click();

    URL.revokeObjectURL(url);
};


// RESET

document.getElementById("reset").onclick = () => {

    if (!confirm("Reset your panel?")) return;

    components = [];
    selected = 0;

    render();
};

render();
