let chatHistory = [];
let authToken = localStorage.getItem("authToken");
let currentUser = JSON.parse(localStorage.getItem("currentUser") || "null");
function formatTimestamp(date = new Date()) {
    return date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
    });
}

function updateCurrentTimestamp() {
    const currentTimestamp = document.getElementById("currentTimestamp");

    if (currentTimestamp) {
        currentTimestamp.textContent = formatTimestamp();
    }
}

setInterval(updateCurrentTimestamp, 1000);
const FAQ_BY_ROLE = {
    admin: [
        { label: "Show all customers", value: "Show all customers" },
        { label: "Show top 10 sales", value: "Show top 10 sales" },
        { label: "Show total sales amount", value: "Show total sales amount" },
        { label: "Highest Sales Employee", value: "Which employee generated the highest sales revenue?" },
        { label: "Employee Count by Department", value: "Show employee count by department" },
        { label: "Recent Orders", value: "Show recent orders" },
        { label: "Monthly Sales Report", value: "Show monthly sales report" },
        { label: "Top Customers by Revenue", value: "Show top customers by revenue" },
        { label: "Show Payment History", value: "Show payment history" },
        { label: "Show Audit Logs", value: "Show audit logs" }
    ],

    sales_manager: [
        { label: "Show all customers", value: "Show all customers" },
        { label: "Show top 10 sales", value: "Show top 10 sales" },
        { label: "Show total sales amount", value: "Show total sales amount" },
        { label: "Highest Sales Employee", value: "Which employee generated the highest sales revenue?" },
        { label: "Monthly Sales Report", value: "Show monthly sales report" },
        { label: "Top Customers by Revenue", value: "Show top customers by revenue" },
        { label: "Show unpaid invoices", value: "Show unpaid invoices" },
        { label: "Show payment history", value: "Show payment history" },
        { label: "Show qualified leads", value: "Show all qualified leads" },
        { label: "Show opportunities in negotiation", value: "Show opportunities in negotiation stage" }
    ],

    sales_executive: [
        { label: "Show all customers", value: "Show all customers" },
        { label: "Customers from Chennai", value: "Show customers from Chennai" },
        { label: "Show qualified leads", value: "Show all qualified leads" },
        { label: "Show proposal sent leads", value: "Show proposal sent leads" },
        { label: "Show top 10 sales", value: "Show top 10 sales" },
        { label: "Recent Orders", value: "Show recent orders" },
        { label: "Show active products", value: "Show all active products" },
        { label: "Show customer feedback", value: "Show all customer feedback" },
        { label: "Customer John Smith journey", value: "Show all activities related to customer John Smith" },
        { label: "Show opportunities in proposal", value: "Show opportunities in proposal stage" }
    ],

    support_executive: [
        { label: "Open Support Tickets", value: "Show all open support tickets" },
        { label: "Critical Tickets", value: "List critical tickets" },
        { label: "Resolved Tickets", value: "Show resolved tickets" },
        { label: "Support History for John Smith", value: "Show support history for customer John Smith" },
        { label: "Customer With Most Tickets", value: "Which customer has the most tickets?" },
        { label: "Show Customer Feedback", value: "Show all customer feedback" },
        { label: "5-Star Ratings", value: "Which customers gave 5-star ratings?" },
        { label: "Recent Orders", value: "Show recent orders" },
        { label: "Software Products", value: "Show products in Software category" },
        { label: "Customer Details", value: "Show customer details for John Smith" }
    ]
};
// LOGIN
async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!username || !password) {
        alert("Enter username and password");
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                password
            })
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.detail || "Invalid Username or Password");
            return;
        }

        authToken = result.token;

        currentUser = {
            username: result.username,
            role: result.role,
            name: result.name
        };

        localStorage.setItem("authToken", authToken);
        localStorage.setItem("currentUser", JSON.stringify(currentUser));

        document.getElementById('loginPage').classList.add('hidden');
        document.getElementById('mainApp').classList.remove('hidden');
        loadFAQList(currentUser.role);
        showLoggedInUser();

    } catch (err) {
        alert("Backend login failed");
    }
}

// LOGOUT
function logout() {
    localStorage.removeItem("authToken");
    localStorage.removeItem("currentUser");

    authToken = null;
    currentUser = null;

    location.reload();
}

// FILL FAQ QUESTION
function fillQuestion(text) {
    document.getElementById('question').value = text;
}
function showLoggedInUser() {
    const roleBox = document.getElementById('loggedInRole');

    if (!roleBox || !currentUser) {
        return;
    }

    roleBox.innerHTML = `
        Logged in as:
        <span class="text-cyan-300 font-black">${currentUser.name}</span>
        <br>
        Role:
        <span class="text-emerald-300 font-black">${currentUser.role}</span>
    `;
}

function loadFAQList(role) {
    const faqSelect = document.getElementById('faqSelect');

    if (!faqSelect) {
        return;
    }

    faqSelect.innerHTML = `<option value="">-- Choose a question --</option>`;

    const questions = FAQ_BY_ROLE[role] || [];

    questions.forEach(item => {
        const option = document.createElement('option');
        option.value = item.value;
        option.textContent = item.label;
        faqSelect.appendChild(option);
    });
}

function useSelectedFAQ() {
    const faqSelect = document.getElementById('faqSelect');

    if (!faqSelect || !faqSelect.value) {
        return false;
    }

    document.getElementById('question').value = faqSelect.value;
    return true;
}

function askSelectedFAQ() {
    const selected = useSelectedFAQ();

    if (!selected) {
        alert("Please select a FAQ question");
        return;
    }

    askQuestion();
}
// CLEAR CHAT
function clearChat() {
    document.getElementById('chatContainer').innerHTML = "";
    chatHistory = [];
}

// DOWNLOAD CHAT
function downloadChat() {
    let content = chatHistory.join("\n\n");

    const blob = new Blob([content], { type: "text/plain" });

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "chat_history.txt";
    a.click();
}

// MAIN API CALL
async function askQuestion() {
    const question = document.getElementById('question').value;

    if (!question) {
        alert("Enter Question");
        return;
    }

    if (!authToken) {
        alert("Please login again");
        return;
    }

    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ question })
        });

        const result = await response.json();

        loading.classList.add('hidden');

        if (!response.ok) {
            alert(result.detail || result.error || "Request failed");
            return;
        }

        if (result.error) {
            alert(result.error);
            return;
        }

        renderChat(question, result);

    } catch (err) {
        loading.classList.add('hidden');
        alert("Backend connection failed");
    }
}

// RENDER CHAT
function renderChat(question, result) {
    const container = document.getElementById('chatContainer');
    const questionTime = formatTimestamp();
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const userDiv = document.createElement('div');
    userDiv.className = "ml-auto w-fit max-w-[78%] rounded-3xl rounded-tr-md bg-gradient-to-br from-emerald-500/25 to-teal-500/20 border border-emerald-400/30 p-5 text-slate-100 fade-in shadow-lg shadow-emerald-500/10";
    userDiv.innerHTML = `
    <div class="flex items-center justify-between gap-4 mb-2">
        <div class="flex items-center gap-2 font-black text-emerald-300">
            <span class="w-2 h-2 rounded-full bg-emerald-300"></span>
            You
        </div>

        <div class="text-xs text-slate-400">
            Asked at: ${questionTime}
        </div>
    </div>

    <div class="text-slate-100 leading-relaxed">${question}</div>
    `;
    container.appendChild(userDiv);

    const aiDiv = document.createElement('div');
    aiDiv.className = "w-fit max-w-[92%] rounded-3xl rounded-tl-md bg-slate-900/80 border border-slate-700/80 p-5 text-slate-100 fade-in shadow-xl shadow-black/20";

    let tableHTML = "";

    if (result.data && result.data.length > 0) {
        tableHTML += `
        <div class="overflow-x-auto mt-5 rounded-2xl border border-slate-700">
            <table class="w-full text-sm">
                <thead>
                    <tr class="bg-slate-800/90">
        `;

        result.columns.forEach(col => {
            tableHTML += `<th class="border border-slate-700 p-3 text-left text-emerald-300 font-black whitespace-nowrap">${col}</th>`;
        });

        tableHTML += `
                    </tr>
                </thead>
                <tbody>
        `;

        result.data.forEach(row => {
            tableHTML += `<tr class="hover:bg-slate-800/70 transition">`;

            result.columns.forEach(col => {
                tableHTML += `<td class="border border-slate-700 p-3 text-slate-200 whitespace-nowrap">${row[col]}</td>`;
            });

            tableHTML += `</tr>`;
        });

        tableHTML += `
                </tbody>
            </table>
        </div>
        `;
    }

    aiDiv.innerHTML = `
        <div class="flex items-center gap-2 font-black mb-3 text-amber-300">
            <span class="w-2 h-2 rounded-full bg-amber-300"></span>
            AI Assistant
        </div>

        <div class="rounded-2xl bg-black/70 border border-emerald-400/20 p-4 font-mono text-sm text-emerald-200 overflow-x-auto">
            ${result.sql || ""}
        </div>

        <div class="mt-4 text-slate-200 leading-relaxed">
            ${result.answer || ""}
        </div>

        ${tableHTML}
    `;

    container.appendChild(aiDiv);
    container.scrollTop = container.scrollHeight;

    chatHistory.push(`
TIME:
${questionTime}

USER:
${question}

SQL:
${result.sql}

ANSWER:
${JSON.stringify(result.data, null, 2)}
`);
}

window.addEventListener("load", () => {
    updateCurrentTimestamp();
    if (authToken && currentUser) {
        document.getElementById('loginPage').classList.add('hidden');
        document.getElementById('mainApp').classList.remove('hidden');
    }
});
window.addEventListener("load", () => {
    if (authToken && currentUser) {
        document.getElementById('loginPage').classList.add('hidden');
        document.getElementById('mainApp').classList.remove('hidden');

        loadFAQList(currentUser.role);
        showLoggedInUser();
    }
});