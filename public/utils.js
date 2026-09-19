// Shared utility functions for DataFlow

// ── Dark Mode Toggle ─────────────────────────────────────────────────────
(function initTheme() {
    const saved = localStorage.getItem('df-theme');
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('themeToggle');
    if (toggle) {
        // Set initial text
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        toggle.textContent = isDark ? 'White' : 'Dark';

        toggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            if (next === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
            localStorage.setItem('df-theme', next);
            toggle.textContent = next === 'dark' ? 'White' : 'Dark';
        });
    }
});

function createSmartTable(rawResult, containerEl) {
    const rows = rawResult.trim().split('\n');
    if (rows.length === 0) return;
    
    const headers = rows[0].split(' | ');
    
    const wrapper = document.createElement('div');
    wrapper.className = 'smart-table-wrapper';
    
    const toolbar = document.createElement('div');
    toolbar.className = 'table-toolbar';
    toolbar.style.cssText = 'display:flex; justify-content:space-between; margin-bottom:0.5rem; align-items:center; margin-top: 1rem;';
    
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Filter rows...';
    searchInput.className = 'table-search';
    searchInput.style.cssText = 'padding:4px 8px; border-radius:4px; border:1px solid #ccc; font-size:0.85rem; background: var(--card-bg); color: var(--text-main); max-width: 60%;';
    
    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn-dashboard';
    exportBtn.innerText = '📥 CSV';
    exportBtn.style.padding = '4px 8px';
    exportBtn.style.fontSize = '0.85rem';
    
    toolbar.appendChild(searchInput);
    toolbar.appendChild(exportBtn);
    
    const tableContainer = document.createElement('div');
    tableContainer.className = 'table-container';
    tableContainer.style.marginTop = '0';
    
    const table = document.createElement('table');
    table.className = 'data-table';
    
    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');
    headers.forEach((h, index) => {
        const th = document.createElement('th');
        th.innerText = h + ' ⇅';
        th.style.cursor = 'pointer';
        th.title = "Click to sort";
        th.addEventListener('click', () => sortTable(table, index));
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);
    
    const tbody = document.createElement('tbody');
    for (let i = 1; i < rows.length; i++) {
        const cells = rows[i].split(' | ');
        const tr = document.createElement('tr');
        cells.forEach(c => {
            const td = document.createElement('td');
            td.innerText = c;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    tableContainer.appendChild(table);
    
    wrapper.appendChild(toolbar);
    wrapper.appendChild(tableContainer);
    
    containerEl.innerHTML = '';
    containerEl.appendChild(wrapper);
    
    // Search functionality
    searchInput.addEventListener('input', (e) => {
        const filter = e.target.value.toLowerCase();
        const trs = tbody.querySelectorAll('tr');
        trs.forEach(tr => {
            const text = tr.innerText.toLowerCase();
            tr.style.display = text.includes(filter) ? '' : 'none';
        });
    });
    
    // CSV Export functionality
    exportBtn.addEventListener('click', () => {
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += headers.join(",") + "\n";
        for (let i = 1; i < rows.length; i++) {
            const cells = rows[i].split(' | ');
            const rowStr = cells.map(c => `"${c.replace(/"/g, '""')}"`).join(",");
            csvContent += rowStr + "\n";
        }
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "data_export.csv");
        document.body.appendChild(link);
        link.click();
        link.remove();
    });
}

function sortTable(table, colIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const isAscending = table.dataset.sortDir === 'asc' && table.dataset.sortCol == colIndex;
    
    rows.sort((a, b) => {
        const aVal = a.cells[colIndex].innerText;
        const bVal = b.cells[colIndex].innerText;
        const aNum = parseFloat(aVal.replace(/[^0-9.-]+/g,""));
        const bNum = parseFloat(bVal.replace(/[^0-9.-]+/g,""));
        
        const aIsNum = !isNaN(aNum) && aVal.match(/[0-9]/);
        const bIsNum = !isNaN(bNum) && bVal.match(/[0-9]/);
        
        if (aIsNum && bIsNum) {
            return isAscending ? bNum - aNum : aNum - bNum;
        }
        return isAscending ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
    });
    
    table.dataset.sortDir = isAscending ? 'desc' : 'asc';
    table.dataset.sortCol = colIndex;
    
    tbody.innerHTML = '';
    rows.forEach(r => tbody.appendChild(r));
}
