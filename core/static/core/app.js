/* AskMyData — SPA navigation + all feature logic.
   Views: dashboard, ask, focus (market deep-dive), explorer, history, settings. */
(function () {
    "use strict";
    const cfg = window.ASKMYDATA;
    const $ = (id) => document.getElementById(id);
    const charts = {};
    const loaded = {};
    const BLUE = "#0787f9";
    const ORANGE = "#ffae43";
    const PURPLE = "#9147d8";
    const RED = "#ff5d67";
    const GREEN = "#76bd32";
    const PALETTE = [BLUE, ORANGE, PURPLE, RED, "#25b7c7", GREEN, "#5768e5", "#ff8654"];
    const VIEW_ROUTES = {
        dashboard: "/dashboard/",
        ask: "/ask-ai/",
        focus: "/market-focus/",
        radar: "/anomaly-radar/",
        explorer: "/data-explorer/",
        history: "/history/",
        settings: "/settings/",
    };
    const ROUTE_VIEWS = Object.fromEntries(
        Object.entries(VIEW_ROUTES).map(([view, route]) => [route, view])
    );

    function movingAverage(values) {
        return values.map((value, index) => {
            const start = Math.max(0, index - 1);
            const slice = values.slice(start, index + 2).map(Number);
            return slice.reduce((sum, current) => sum + current, 0) / slice.length;
        });
    }

    function benchmark(values) {
        const average = values.map(Number).reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
        return values.map(() => average);
    }

    // ---- helpers ----------------------------------------------------------
    function esc(s) {
        return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    function fmtNum(v) {
        if (v === null || v === undefined || v === "") return "";
        if (typeof v === "number") {
            return Number.isInteger(v) ? v.toLocaleString()
                : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
        }
        return v;
    }
    function fmtMoney(v) {
        const n = Number(v) || 0;
        if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
        if (n >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
        if (n >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
        return "$" + n.toFixed(0);
    }
    function fmtCompact(v) {
        const n = Number(v) || 0;
        if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
        if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
        return String(n);
    }
    const show = (el) => { el.hidden = false; };
    const hide = (el) => { el.hidden = true; };
    const getJSON = (url) => fetch(url).then((r) => r.json());
    const postJSON = (url, body) => fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrfToken },
        body: JSON.stringify(body),
    }).then((r) => r.json());

    function skel(n, cls) {
        let h = "";
        for (let i = 0; i < n; i++) h += '<div class="skel ' + cls + '"></div>';
        return h;
    }

    function drawChart(id, type, labels, values, label, opts) {
        opts = opts || {};
        if (charts[id]) charts[id].destroy();
        const canvas = document.getElementById(id);
        if (!canvas) return;
        const isCircular = type === "pie" || type === "doughnut" || type === "polarArea";
        const numericValues = values.map(Number);
        const datasets = [];

        if (type === "line") {
            datasets.push({
                label: label || "Revenue",
                data: numericValues,
                borderColor: BLUE,
                backgroundColor: "transparent",
                borderWidth: 2,
                tension: 0.42,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: "#fff",
                pointBorderColor: BLUE,
                pointBorderWidth: 1.5,
            });
            if (opts.trendLines) {
                datasets.push({
                    label: "Moving average",
                    data: movingAverage(numericValues),
                    borderColor: ORANGE,
                    backgroundColor: "transparent",
                    borderWidth: 1.6,
                    tension: 0.42,
                    pointRadius: 2.5,
                    pointBackgroundColor: "#fff",
                    pointBorderColor: ORANGE,
                    pointBorderWidth: 1.2,
                });
                datasets.push({
                    label: "Benchmark",
                    data: benchmark(numericValues),
                    borderColor: PURPLE,
                    backgroundColor: "transparent",
                    borderWidth: 1.4,
                    borderDash: [5, 4],
                    tension: 0,
                    pointRadius: 0,
                });
            }
        } else {
            datasets.push({
                label: label || "",
                data: numericValues,
                backgroundColor: isCircular
                    ? labels.map((_, index) => PALETTE[index % PALETTE.length])
                    : labels.map((_, index) => opts.multicolor ? PALETTE[index % PALETTE.length] : BLUE),
                borderColor: isCircular ? "#fff" : "transparent",
                borderWidth: isCircular ? 3 : 0,
                borderRadius: isCircular ? 0 : 2,
                hoverOffset: isCircular ? 5 : 0,
            });
        }

        charts[id] = new Chart(canvas.getContext("2d"), {
            type: type === "line" ? "line" : isCircular ? type : "bar",
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 650, easing: "easeOutQuart" },
                interaction: { intersect: false, mode: "index" },
                plugins: {
                    legend: {
                        display: isCircular || Boolean(opts.trendLines),
                        position: isCircular ? "right" : "bottom",
                        align: isCircular ? "center" : "start",
                        labels: {
                            color: "#89909a",
                            usePointStyle: true,
                            pointStyle: "circle",
                            boxWidth: 6,
                            boxHeight: 6,
                            padding: 16,
                            font: { family: "Inter", size: 11 },
                        },
                    },
                    tooltip: {
                        backgroundColor: "#242a33",
                        titleFont: { family: "Inter", size: 10 },
                        bodyFont: { family: "Inter", size: 10 },
                        padding: 9,
                        cornerRadius: 2,
                        callbacks: opts.money ? { label: (context) => {
                            const parsed = context.parsed;
                            const value = parsed && typeof parsed === "object" ? (parsed.y ?? parsed.r ?? 0) : parsed;
                            return " " + context.dataset.label + ": " + fmtMoney(value);
                        } } : {},
                    },
                },
                scales: isCircular ? {} : {
                    x: {
                        ticks: { color: "#9ca2aa", font: { family: "Inter", size: 11 } },
                        grid: { color: "#f0f1f3", drawTicks: false },
                        border: { display: false },
                    },
                    y: {
                        beginAtZero: type !== "line",
                        ticks: {
                            color: "#9ca2aa",
                            padding: 8,
                            font: { family: "Inter", size: 11 },
                            callback: (value) => opts.money ? fmtMoney(value) : fmtCompact(value),
                        },
                        grid: { color: "#eef0f2", drawTicks: false },
                        border: { display: false },
                    },
                },
            },
        });
    }

    function drawLogisticsRadar(labels, values) {
        if (charts.chShip) charts.chShip.destroy();
        const total = values.map(Number).reduce((sum, value) => sum + value, 0) || 1;
        const shares = values.map((value) => Number(value) / total * 100);
        const maxShare = Math.max(20, Math.ceil(Math.max(...shares) / 5) * 5);
        charts.chShip = new Chart($("chShip").getContext("2d"), {
            type: "radar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Shipment share",
                    data: shares,
                    borderColor: PURPLE,
                    backgroundColor: "rgba(145,71,216,.14)",
                    pointBackgroundColor: ORANGE,
                    pointBorderColor: "#fff",
                    pointBorderWidth: 1.2,
                    pointRadius: 3,
                    borderWidth: 1.8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (context) => " " + context.parsed.r.toFixed(1) + "% of shipments" } },
                },
                scales: {
                    r: {
                        min: 0,
                        max: maxShare,
                        ticks: { display: false },
                        grid: { color: "#e9e3f0" },
                        angleLines: { color: "#ece7f2" },
                        pointLabels: { color: "#8e8498", font: { family: "Inter", size: 10, weight: "600" } },
                    },
                },
            },
        });
    }

    function renderSegmentConstellation(labels, values) {
        const root = $("segmentConstellation");
        const width = 920, height = 250, centerX = 460, centerY = 125;
        const numeric = values.map(Number);
        const total = numeric.reduce((sum, value) => sum + value, 0) || 1;
        const min = Math.min(...numeric), max = Math.max(...numeric);
        let svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Market segment orbital revenue constellation">';
        svg += '<defs><filter id="orbitGlow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
        svg += '<ellipse class="orbit-ring" cx="' + centerX + '" cy="' + centerY + '" rx="315" ry="93"/><ellipse class="orbit-ring inner" cx="' + centerX + '" cy="' + centerY + '" rx="205" ry="63"/>';
        labels.forEach((label, index) => {
            const angle = -Math.PI / 2 + (Math.PI * 2 * index / labels.length);
            const x = centerX + Math.cos(angle) * 315;
            const y = centerY + Math.sin(angle) * 92;
            const ratio = max === min ? .5 : (numeric[index] - min) / (max - min);
            const radius = 26 + ratio * 15;
            const color = PALETTE[index % PALETTE.length];
            svg += '<line class="orbit-link" x1="' + centerX + '" y1="' + centerY + '" x2="' + x + '" y2="' + y + '" stroke="' + color + '"/>';
            svg += '<circle class="orbit-node" cx="' + x + '" cy="' + y + '" r="' + radius + '" fill="' + color + '"><title>' + esc(label + ": " + fmtMoney(numeric[index])) + '</title></circle>';
            svg += '<text class="orbit-label" x="' + x + '" y="' + (y - 2) + '">' + esc(label) + '</text><text class="orbit-value" x="' + x + '" y="' + (y + 11) + '">' + esc((numeric[index] / total * 100).toFixed(1) + "%") + '</text>';
        });
        svg += '<circle class="orbit-core" cx="' + centerX + '" cy="' + centerY + '" r="48"/><text class="orbit-core-kicker" x="' + centerX + '" y="' + (centerY - 5) + '">TOTAL REVENUE</text><text class="orbit-core-value" x="' + centerX + '" y="' + (centerY + 16) + '">' + esc(fmtMoney(total)) + '</text></svg>';
        root.innerHTML = svg;
    }

    function renderTable(tableEl, columns, rows) {
        let h = "<thead><tr>";
        columns.forEach((c) => (h += "<th>" + esc(c) + "</th>"));
        h += "</tr></thead><tbody>";
        rows.forEach((r) => {
            h += "<tr>";
            r.forEach((c) => (h += "<td>" + esc(fmtNum(c)) + "</td>"));
            h += "</tr>";
        });
        tableEl.innerHTML = h + "</tbody>";
    }
    function errBox(msg) { return '<div class="error-box" style="grid-column:1/-1">' + esc(msg || "Failed to load.") + "</div>"; }

    // ---- navigation + persistent URL routing -----------------------------
    function routeForCurrentPath() {
        const path = window.location.pathname.endsWith("/")
            ? window.location.pathname
            : window.location.pathname + "/";
        return ROUTE_VIEWS[path] || (path === "/" ? "dashboard" : "dashboard");
    }

    function switchView(name, updateUrl = true) {
        if (!VIEW_ROUTES[name]) name = "dashboard";
        document.querySelectorAll(".nav-item").forEach((button) =>
            button.classList.toggle("active", button.dataset.view === name));
        document.querySelectorAll(".rail-link").forEach((button) =>
            button.classList.toggle("active", button.dataset.view === name));
        document.querySelectorAll(".view").forEach((view) =>
            view.classList.toggle("active", view.id === "view-" + name));

        if (updateUrl && window.location.pathname !== VIEW_ROUTES[name]) {
            window.history.pushState({ view: name }, "", VIEW_ROUTES[name]);
        }
        document.title = "AskMyData · " + name.replace(/(^|_)(\w)/g, (_, _prefix, letter) => letter.toUpperCase());
        window.scrollTo({ top: 0, behavior: updateUrl ? "smooth" : "auto" });

        if (name === "dashboard" && !loaded.dashboard) loadDashboard();
        if (name === "focus" && !loaded.nations) loadNations();
        if (name === "radar" && !loaded.radar) loadRadar();
        if (name === "explorer" && !loaded.explorer) loadTables();
        if (name === "history") renderHistory();
        if (name === "settings" && !loaded.settings) loadSettings();
    }
    document.querySelectorAll(".nav-item, .rail-link, .rail-target").forEach((button) =>
        button.addEventListener("click", () => switchView(button.dataset.view)));
    window.addEventListener("popstate", () => switchView(routeForCurrentPath(), false));

    document.querySelectorAll(".period-tabs button").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".period-tabs button").forEach((tab) => tab.classList.remove("active"));
            button.classList.add("active");
        });
    });

    // ---- health -----------------------------------------------------------
    function loadHealth() {
        return getJSON(cfg.healthUrl).then((d) => {
            const dot = $("connDot"), label = $("connLabel");
            if (d.ok) { dot.className = "conn ok"; label.textContent = "Snowflake connected"; }
            else { dot.className = "conn bad"; label.textContent = "not connected"; }
        }).catch(() => { $("connDot").className = "conn bad"; $("connLabel").textContent = "offline"; });
    }

    // ---- DASHBOARD --------------------------------------------------------
    function setDashboardLoading(isLoading) {
        document.querySelectorAll("#view-dashboard .chart-primary, #view-dashboard .dashboard-bottom .analytics-panel, #view-dashboard > .full-panel").forEach((panel) =>
            panel.classList.toggle("loading-panel", isLoading));
    }
    function dashSkeleton() {
        $("kpis").innerHTML = skel(4, "skel-kpi");
        setDashboardLoading(true);
    }
    function loadDashboard() {
        dashSkeleton();
        getJSON(cfg.dashboardUrl).then((d) => {
            if (!d.ok) {
                $("kpis").innerHTML = errBox(d.error);
                setDashboardLoading(false);
                return;
            }
            loaded.dashboard = true;
            const k = d.kpis;
            $("kpis").innerHTML =
                kpi("c1", "Total revenue", fmtMoney(k.revenue), "7.0% since last period", "↗") +
                kpi("c2", "Customers", fmtNum(k.customers), "Live customer base", "♙") +
                kpi("c3", "Orders", fmtNum(k.orders), "Processed in Snowflake", "▥") +
                kpi("c4", "Suppliers", fmtNum(k.suppliers), "Connected partners", "◎");
            const c = d.charts;
            drawChart("chYear", "line", c.revenue_by_year.labels, c.revenue_by_year.values, "Revenue", { money: true, trendLines: true });
            drawChart("chRegion", "polarArea", c.revenue_by_region.labels, c.revenue_by_region.values, "Regional exposure", { money: true, multicolor: true });
            drawLogisticsRadar(c.shipments_by_mode.labels, c.shipments_by_mode.values);
            renderSegmentConstellation(c.revenue_by_segment.labels, c.revenue_by_segment.values);
            setDashboardLoading(false);
        }).catch((e) => {
            $("kpis").innerHTML = errBox(e.message);
            setDashboardLoading(false);
        });
    }
    function kpi(cls, label, value, sub, icon, subIsHtml) {
        const subContent = subIsHtml ? sub : esc(sub);
        return '<div class="kpi ' + cls + '">' +
            '<span class="kpi-icon">' + esc(icon || "↗") + '</span>' +
            '<div class="label">' + esc(label) + '</div>' +
            '<div class="value">' + esc(value) + '</div>' +
            '<div class="sub">' + subContent + '</div></div>';
    }
    $("refreshDash").addEventListener("click", () => { loaded.dashboard = false; loadDashboard(); });

    // ---- ASK AI -----------------------------------------------------------
    const STEP_ICONS = { "Planner": "◱", "SQL Generator": "⚙", "SQL Generator (retry)": "⟳",
        "Critic": "◎", "Execute on Snowflake": "❄", "Insight": "✦", "Error": "!" };
    function askSubmit() {
        const q = $("question").value.trim();
        if (!q) return;
        setBtn($("askBtn"), true, "Analyzing");
        hide($("askResults")); hide($("askError"));
        show($("pipeline"));
        $("steps").innerHTML = '<div class="step"><div class="ico">✦</div><div><div class="name">Working…</div>' +
            '<div class="detail">Planning, querying Snowflake, checking and explaining.</div></div></div>';
        postJSON(cfg.askUrl, { question: q })
            .then((res) => { renderAsk(res); if (res.ok) addHistory(q); })
            .catch((e) => { $("askError").textContent = "Network error: " + e.message; show($("askError")); })
            .finally(() => setBtn($("askBtn"), false, "Analyze"));
    }
    function renderAsk(res) {
        $("steps").innerHTML = "";
        (res.steps || []).forEach((s, i) => {
            const isCode = s.name.indexOf("SQL Generator") === 0;
            const div = document.createElement("div");
            div.className = "step " + (s.status || "");
            div.style.animationDelay = (i * 80) + "ms";
            div.innerHTML = '<div class="ico">' + (STEP_ICONS[s.name] || "•") + '</div>' +
                '<div><div class="name">' + esc(s.name) + '</div>' +
                '<div class="detail ' + (isCode ? "code" : "") + '">' + esc(s.detail || "") + '</div></div>';
            $("steps").appendChild(div);
        });
        if (!res.ok) { $("askError").textContent = res.error || "Something went wrong."; show($("askError")); return; }
        hide($("askError"));
        $("headline").textContent = res.headline || "";
        $("insightBody").textContent = res.insight || "";
        $("action").textContent = res.action || "";
        $("action").style.display = res.action ? "" : "none";
        $("sqlBox").textContent = res.sql || "";
        $("rowCount").textContent = (res.row_count || 0) + " rows";
        renderTable($("askTable"), res.columns || [], res.rows || []);
        if (res.chart && res.chart.values && res.chart.values.length) {
            show($("chartCard"));
            drawChart("askChart", res.chart.type, res.chart.labels, res.chart.values, res.chart.value_label || "", { multicolor: true });
        } else { hide($("chartCard")); }
        show($("askResults"));
    }
    $("askBtn").addEventListener("click", askSubmit);
    $("question").addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") askSubmit(); });
    document.querySelectorAll(".chip").forEach((c) =>
        c.addEventListener("click", () => { $("question").value = c.dataset.q; askSubmit(); }));

    // ---- MARKET FOCUS -----------------------------------------------------
    function loadNations() {
        getJSON(cfg.nationsUrl).then((d) => {
            if (!d.ok) { $("focusError").textContent = d.error; show($("focusError")); return; }
            loaded.nations = true;
            const sel = $("nationSelect");
            sel.innerHTML = d.nations.map((n) => '<option value="' + esc(n) + '">' + esc(n) + '</option>').join("");
            const pref = d.nations.indexOf("INDIA");
            if (pref >= 0) sel.selectedIndex = pref;
        });
    }
    function runFocus() {
        const nation = $("nationSelect").value;
        if (!nation) return;
        setBtn($("focusBtn"), true, "Analyzing");
        hide($("focusError")); hide($("focusEmpty")); hide($("focusOut"));
        // skeleton
        $("focusKpis").innerHTML = skel(4, "skel-kpi");
        show($("focusOut"));
        $("focusSummary").innerHTML = '<div class="skel skel-line w80"></div><div class="skel skel-line w60"></div>';
        getJSON(cfg.focusUrl + encodeURIComponent(nation) + "/").then((d) => {
            if (!d.ok) { hide($("focusOut")); $("focusError").textContent = d.error || "Failed."; show($("focusError")); return; }
            renderFocus(d);
        }).catch((e) => { hide($("focusOut")); $("focusError").textContent = e.message; show($("focusError")); })
          .finally(() => setBtn($("focusBtn"), false, "Analyze market"));
    }
    function renderFocus(d) {
        const vs = d.vs_average_pct;
        const vsClass = vs >= 0 ? "up" : "down";
        const vsText = (vs >= 0 ? "+" : "") + vs + "% vs avg market";
        $("focusRank").innerHTML = d.rank ? ('Rank <b>#' + d.rank + '</b> of ' + d.nation_count + ' markets') : "";
        $("focusKpis").innerHTML =
            kpi("c1", "Market revenue", fmtMoney(d.revenue), '<span class="badge ' + vsClass + '">' + vsText + '</span>', "↗", true) +
            kpi("c2", "Orders", fmtNum(d.orders), "in this market", "▥") +
            kpi("c3", "Customers", fmtNum(d.customers), "in this market", "♙") +
            kpi("c4", "Rank", "#" + (d.rank || "-"), "of " + d.nation_count + " markets", "◎");

        const ai = d.ai || {};
        $("focusSummary").textContent = ai.summary || ("Market analysis for " + d.nation);

        drawChart("chFocusTrend", "line", d.trend.labels, d.trend.values, "Revenue", { money: true });

        // segment mix vs average: two datasets
        const sc = d.segment_compare || [];
        if (charts.chFocusSeg) charts.chFocusSeg.destroy();
        charts.chFocusSeg = new Chart($("chFocusSeg").getContext("2d"), {
            type: "bar",
            data: {
                labels: sc.map((s) => s.segment),
                datasets: [
                    { label: "This market %", data: sc.map((s) => s.nation_share), backgroundColor: BLUE, borderRadius: 2 },
                    { label: "Average market %", data: sc.map((s) => s.global_share), backgroundColor: ORANGE, borderRadius: 2 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", align: "start", labels: { color: "#89909a", usePointStyle: true, pointStyle: "circle", boxWidth: 6, padding: 14, font: { family: "Inter", size: 11 } } },
                    tooltip: { backgroundColor: "#242a33", cornerRadius: 2, padding: 9 },
                },
                scales: {
                    x: { ticks: { color: "#9ca2aa", font: { family: "Inter", size: 10 } }, grid: { display: false }, border: { display: false } },
                    y: { beginAtZero: true, ticks: { color: "#9ca2aa", font: { family: "Inter", size: 11 }, callback: (v) => v + "%" }, grid: { color: "#eef0f2" }, border: { display: false } },
                },
            },
        });

        drawChart("chFocusTypes", "bar", d.product_types.labels, d.product_types.values, "Revenue", { money: true, multicolor: true });

        $("focusStrengths").innerHTML = (ai.strengths || []).length
            ? ai.strengths.map((s) => insItem(s.title, s.detail)).join("")
            : '<div class="ins-item"><div class="d">No standout strengths detected.</div></div>';
        $("focusWeak").innerHTML = (ai.weaknesses || []).length
            ? ai.weaknesses.map((w) => insItem(w.title, w.reason)).join("")
            : '<div class="ins-item"><div class="d">No major weak spots detected.</div></div>';
        $("focusRecs").innerHTML = (ai.recommendations || []).map((r) => "<li>" + esc(r) + "</li>").join("")
            || "<li>Keep monitoring this market.</li>";
    }
    function insItem(t, d) {
        return '<div class="ins-item"><div class="t">' + esc(t || "") + '</div><div class="d">' + esc(d || "") + '</div></div>';
    }
    $("focusBtn").addEventListener("click", runFocus);

    // ---- ANOMALY RADAR ---------------------------------------------------
    function loadRadar() {
        const button = $("scanBtn");
        setBtn(button, true, "Scanning");
        $("scanStatus").textContent = "Scanning Snowflake signals…";
        document.querySelector(".radar-command").classList.add("scanning");
        hide($("radarEmpty"));
        hide($("radarError"));

        getJSON(cfg.anomalyUrl).then((data) => {
            if (!data.ok) {
                $("radarError").textContent = data.error || "Anomaly scan failed.";
                show($("radarError"));
                show($("radarEmpty"));
                return;
            }
            loaded.radar = true;
            renderRadar(data);
            $("scanStatus").textContent = "Scan complete · monitoring active";
            show($("radarOut"));
        }).catch((error) => {
            $("radarError").textContent = error.message;
            show($("radarError"));
            show($("radarEmpty"));
        }).finally(() => {
            document.querySelector(".radar-command").classList.remove("scanning");
            setBtn(button, false, "Scan again");
        });
    }

    function renderRadar(data) {
        const meta = data.meta || {};
        $("anomalyMeta").innerHTML =
            radarMetric("signal", "Signals scanned", fmtNum(meta.signals_scanned || 0), "Snowflake rows evaluated") +
            radarMetric("warning", "Anomalies", fmtNum(meta.anomalies_found || 0), "|z| ≥ " + (meta.threshold || 0)) +
            radarMetric("critical", "Critical", fmtNum(meta.critical_count || 0), fmtNum(meta.data_quality_count || 0) + " data-quality alert(s)") +
            radarMetric("health", "Signal health", fmtNum(meta.health_score || 0) + "%", meta.engine || "SQL engine");
        $("signalCount").textContent = (meta.anomalies_found || 0) + " SIGNALS";

        renderRiskRadar(data.radar || []);
        renderHeatmap(data.heatmap || {});
        renderNetwork(data.network || []);
        renderAnomalyFeed(data.anomalies || []);
        renderInvestigation(data.ai || {});
    }

    function radarMetric(kind, label, value, detail) {
        return '<div class="radar-metric ' + kind + '"><span class="metric-beacon"></span>' +
            '<div><small>' + esc(label) + '</small><strong>' + esc(value) + '</strong><em>' + esc(detail) + '</em></div></div>';
    }

    function renderRiskRadar(items) {
        if (charts.chRiskRadar) charts.chRiskRadar.destroy();
        const labels = items.map((item) => item.segment);
        charts.chRiskRadar = new Chart($("chRiskRadar").getContext("2d"), {
            type: "radar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Risk signature",
                        data: items.map((item) => item.risk),
                        borderColor: RED,
                        backgroundColor: "rgba(255,93,103,.18)",
                        pointBackgroundColor: RED,
                        pointBorderColor: "#ffb8bd",
                        borderWidth: 1.8,
                        pointRadius: 2.5,
                    },
                    {
                        label: "Stability shield",
                        data: items.map((item) => item.stability),
                        borderColor: "#20d7ff",
                        backgroundColor: "rgba(32,215,255,.08)",
                        pointBackgroundColor: "#20d7ff",
                        borderWidth: 1.4,
                        pointRadius: 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 850 },
                plugins: {
                    legend: { position: "bottom", labels: { color: "#657180", usePointStyle: true, boxWidth: 7, font: { family: "Inter", size: 11 } } },
                    tooltip: { backgroundColor: "#09111d", borderColor: "#1d3854", borderWidth: 1 },
                },
                scales: {
                    r: {
                        min: 0, max: 100,
                        ticks: { display: false, stepSize: 20 },
                        grid: { color: "rgba(91,143,181,.22)" },
                        angleLines: { color: "rgba(91,143,181,.24)" },
                        pointLabels: { color: "#607184", font: { family: "Inter", size: 11, weight: "600" } },
                    },
                },
            },
        });
    }

    function renderHeatmap(heatmap) {
        const years = heatmap.years || [];
        const segments = heatmap.segments || [];
        const map = new Map((heatmap.cells || []).map((cell) => [cell.segment + "|" + cell.year, cell]));
        const root = $("anomalyHeatmap");
        root.style.gridTemplateColumns = "minmax(82px, 1.15fr) repeat(" + Math.max(years.length, 1) + ", minmax(38px, 1fr))";
        let html = '<span class="heat-label corner">SEGMENT</span>';
        years.forEach((year) => { html += '<span class="heat-year">' + esc(year) + '</span>'; });
        segments.forEach((segment) => {
            html += '<span class="heat-label">' + esc(segment) + '</span>';
            years.forEach((year) => {
                const cell = map.get(segment + "|" + year) || { score: 0, revenue: 0 };
                const severity = cell.quality_issue ? "data-quality" : cell.score >= 2.5 ? "critical" : cell.score >= 1.7 ? "elevated" : cell.score >= 1 ? "watch" : "stable";
                const cellLabel = cell.quality_issue ? "DQ" : Number(cell.score).toFixed(1);
                html += '<button class="heat-cell ' + severity + '" title="' + esc(segment + " · " + year + " · " + cell.score + "σ · " + fmtMoney(cell.revenue) + (cell.quality_issue ? " · incomplete period" : "")) + '">' +
                    '<span>' + cellLabel + '</span></button>';
            });
        });
        root.innerHTML = html;
    }

    function renderNetwork(edges) {
        const root = $("marketNetwork");
        if (!edges.length) { root.innerHTML = '<div class="network-empty">No relationship signals.</div>'; return; }
        const regions = [...new Set(edges.map((edge) => edge.region))];
        const segments = [...new Set(edges.map((edge) => edge.segment))];
        const width = 920, height = 330, leftX = 130, rightX = 790;
        const leftGap = height / (regions.length + 1);
        const rightGap = height / (segments.length + 1);
        const regionY = Object.fromEntries(regions.map((name, index) => [name, leftGap * (index + 1)]));
        const segmentY = Object.fromEntries(segments.map((name, index) => [name, rightGap * (index + 1)]));
        const maxRevenue = Math.max(...edges.map((edge) => Number(edge.revenue)), 1);
        let svg = '<svg viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Region to segment revenue relationship graph">';
        svg += '<defs><filter id="nodeGlow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>';
        edges.forEach((edge, index) => {
            const y1 = regionY[edge.region], y2 = segmentY[edge.segment];
            const stroke = PALETTE[index % PALETTE.length];
            const thickness = .65 + (Number(edge.revenue) / maxRevenue) * 3.4;
            svg += '<path class="network-edge" d="M' + leftX + ',' + y1 + ' C360,' + y1 + ' 560,' + y2 + ' ' + rightX + ',' + y2 + '" stroke="' + stroke + '" stroke-width="' + thickness.toFixed(2) + '"><title>' + esc(edge.region + " → " + edge.segment + ": " + fmtMoney(edge.revenue)) + '</title></path>';
        });
        regions.forEach((name, index) => {
            const y = regionY[name], color = PALETTE[index % PALETTE.length];
            svg += '<circle class="network-node" cx="' + leftX + '" cy="' + y + '" r="7" fill="' + color + '"/><text class="network-label left" x="' + (leftX - 14) + '" y="' + (y + 3) + '">' + esc(name) + '</text>';
        });
        segments.forEach((name, index) => {
            const y = segmentY[name], color = PALETTE[(index + 2) % PALETTE.length];
            svg += '<circle class="network-node" cx="' + rightX + '" cy="' + y + '" r="7" fill="' + color + '"/><text class="network-label" x="' + (rightX + 14) + '" y="' + (y + 3) + '">' + esc(name) + '</text>';
        });
        root.innerHTML = svg + '</svg>';
    }

    function renderAnomalyFeed(anomalies) {
        $("anomalyList").innerHTML = anomalies.length ? anomalies.map((item, index) =>
            '<div class="anomaly-row ' + esc(item.severity) + '">' +
                '<span class="anomaly-index">' + String(index + 1).padStart(2, "0") + '</span>' +
                '<span class="severity-led"></span>' +
                '<div class="anomaly-main"><strong>' + esc(item.segment) + '</strong><small>' + esc(item.period) + ' · ' + esc(item.direction) + ' · ' + esc(item.diagnostic || "statistical anomaly") + '</small></div>' +
                '<div class="anomaly-change">' + (item.change_pct > 0 ? "+" : "") + esc(item.change_pct) + '%</div>' +
                '<div class="sigma">' + esc(item.z_score) + 'σ</div></div>'
        ).join("") : '<div class="network-empty">No anomalies above the configured threshold.</div>';
    }

    function renderInvestigation(ai) {
        $("aiVerdict").textContent = ai.verdict || "Scan complete. Review the detected signals.";
        $("causeList").innerHTML = (ai.likely_causes || []).map((cause) =>
            '<article class="cause-item"><span></span><div><strong>' + esc(cause.signal || "Signal") + '</strong>' +
            '<small>' + esc(cause.evidence || "") + '</small><p>' + esc(cause.reason || "") + '</p></div></article>'
        ).join("");
        $("actionList").innerHTML = (ai.actions || []).map((action) => '<li>' + esc(action) + '</li>').join("");
        $("watchNext").textContent = ai.watch_next || "Highest absolute z-score";
    }

    $("scanBtn").addEventListener("click", loadRadar);

    // ---- DATA EXPLORER ----------------------------------------------------
    function loadTables() {
        $("tableList").innerHTML = skel(6, "skel-line");
        getJSON(cfg.tablesUrl).then((d) => {
            if (!d.ok) { $("tableList").innerHTML = errBox(d.error); return; }
            loaded.explorer = true;
            $("tableList").innerHTML = "";
            d.tables.forEach((t, i) => {
                const b = document.createElement("button");
                b.className = "tbl-btn" + (i === 0 ? " active" : "");
                b.innerHTML = '<span>' + esc(t.name) + '</span><span class="rows">' + fmtNum(t.rows) + '</span>';
                b.addEventListener("click", () => {
                    document.querySelectorAll(".tbl-btn").forEach((x) => x.classList.remove("active"));
                    b.classList.add("active");
                    loadPreview(t.name, t.rows);
                });
                $("tableList").appendChild(b);
            });
            if (d.tables.length) loadPreview(d.tables[0].name, d.tables[0].rows);
        });
    }
    function loadPreview(name, rowCount) {
        $("previewTitle").textContent = name;
        $("previewMeta").textContent = "loading…";
        getJSON(cfg.tableUrl + encodeURIComponent(name) + "/").then((d) => {
            if (!d.ok) { $("previewMeta").textContent = ""; return; }
            $("previewMeta").textContent = "showing " + d.rows.length + " of " + fmtNum(rowCount) + " rows";
            renderTable($("previewTable"), d.columns, d.rows);
        });
    }

    // ---- HISTORY ----------------------------------------------------------
    const HKEY = "askmydata_history";
    const getHistory = () => { try { return JSON.parse(localStorage.getItem(HKEY) || "[]"); } catch (e) { return []; } };
    function addHistory(q) {
        let h = getHistory().filter((x) => x.q !== q);
        h.unshift({ q: q, t: Date.now() });
        localStorage.setItem(HKEY, JSON.stringify(h.slice(0, 25)));
    }
    function renderHistory() {
        const h = getHistory();
        if (!h.length) { show($("historyEmpty")); $("historyList").innerHTML = ""; return; }
        hide($("historyEmpty"));
        $("historyList").innerHTML = "";
        h.forEach((item) => {
            const div = document.createElement("div");
            div.className = "hist-item";
            div.innerHTML = '<span class="q">' + esc(item.q) + '</span><span class="when">' + timeAgo(item.t) + '</span>';
            div.addEventListener("click", () => { switchView("ask"); $("question").value = item.q; askSubmit(); });
            $("historyList").appendChild(div);
        });
    }
    function timeAgo(t) {
        const s = Math.floor((Date.now() - t) / 1000);
        if (s < 60) return "just now";
        if (s < 3600) return Math.floor(s / 60) + "m ago";
        if (s < 86400) return Math.floor(s / 3600) + "h ago";
        return Math.floor(s / 86400) + "d ago";
    }
    $("clearHistory").addEventListener("click", () => { localStorage.removeItem(HKEY); renderHistory(); });

    // ---- SETTINGS ---------------------------------------------------------
    function loadSettings() {
        loaded.settings = true;
        $("settingsGrid").innerHTML = skel(5, "skel-line");
        getJSON(cfg.healthUrl).then((d) => {
            const rows = [
                ["Connection", d.ok ? "Connected" : "Not connected"],
                ["Snowflake version", d.version || "—"],
                ["Warehouse", d.warehouse || "—"],
                ["LLM provider", d.provider || "—"],
                ["Dataset", "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1"],
            ];
            if (d.error) rows.push(["Note", d.error]);
            $("settingsGrid").innerHTML = rows.map((r) =>
                '<div class="k">' + esc(r[0]) + '</div><div class="v">' + esc(r[1]) + '</div>').join("");
        });
    }

    // ---- shared -----------------------------------------------------------
    function setBtn(btn, on, restText) {
        btn.disabled = on;
        btn.querySelector(".btn-text").textContent = on ? restText : restText;
        btn.querySelector(".spin").hidden = !on;
    }

    // ---- init -------------------------------------------------------------
    loadHealth();
    switchView(routeForCurrentPath(), false);
})();
