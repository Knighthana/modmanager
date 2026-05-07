type NotifyPlatform = 'browser' | 'tauri';

let platform: NotifyPlatform = 'browser';

export function setNotifyPlatform(p: NotifyPlatform) {
    platform = p;
}

/** 显示可关闭的气泡提示 */
export function showPopup(content: string, referenceEl: HTMLElement, event?: MouseEvent): void {
    if (platform === 'browser') {
        // 创建临时 div + popover 样式
        const popup = document.createElement('div');
        popup.className = 'notify-popup';
        popup.innerHTML = `
            <div style="max-width:400px;padding:12px;background:var(--el-bg-color);border:1px solid var(--el-border-color);border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:13px;line-height:1.6;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <strong>说明</strong>
                    <span style="cursor:pointer;font-size:16px;" onclick="this.closest('.notify-popup').remove()">×</span>
                </div>
                <div>${content}</div>
            </div>
        `;
        document.body.appendChild(popup);

        // 优先用鼠标坐标，回退到 referenceEl rect
        let left: number, top: number;
        if (event) {
            left = event.clientX + 12;
            top = event.clientY - 8;
        } else {
            const rect = referenceEl.getBoundingClientRect();
            left = rect.right + 8;
            top = rect.top;
        }
        popup.style.position = 'fixed';
        popup.style.left = `${left}px`;
        popup.style.top = `${top}px`;
        popup.style.zIndex = '9999';

        // 点击外部关闭
        const closeOnOutside = (e: MouseEvent) => {
            if (!popup.contains(e.target as Node)) {
                popup.remove();
                document.removeEventListener('click', closeOnOutside);
            }
        };
        setTimeout(() => document.addEventListener('click', closeOnOutside), 10);
    }
    // Tauri platform implementation reserved
}
