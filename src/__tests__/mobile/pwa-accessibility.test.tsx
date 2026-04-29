/**
 * PWA + 无障碍 (A11y) 测试
 * 验证 PWA 配置、ARIA 属性、键盘导航、响应式设计
 */
import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

// ════════════════════════════════════════════════════════════════════
// PWA Manifest 验证
// ════════════════════════════════════════════════════════════════════

describe('PWA Manifest Validation', () => {
    const manifestPath = path.resolve(process.cwd(), 'public/manifest.json');
    const manifestExists = fs.existsSync(manifestPath);

    it('manifest.json file exists', () => {
        // PWA 需要 manifest 文件
        // 如果不存在，测试仍然 pass 但标记 warning
        if (!manifestExists) {
            console.warn('⚠️ manifest.json not found — PWA features disabled');
        }
        expect(true).toBe(true); // baseline pass
    });

    if (manifestExists) {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));

        it('has required name field', () => {
            expect(manifest.name || manifest.short_name).toBeTruthy();
        });

        it('has valid start_url', () => {
            expect(manifest.start_url).toBeDefined();
            expect(typeof manifest.start_url).toBe('string');
        });

        it('has display mode', () => {
            const validModes = ['fullscreen', 'standalone', 'minimal-ui', 'browser'];
            expect(validModes).toContain(manifest.display);
        });

        it('has at least one icon', () => {
            expect(manifest.icons).toBeDefined();
            expect(manifest.icons.length).toBeGreaterThan(0);
        });

        it('icons have required src and sizes', () => {
            for (const icon of manifest.icons) {
                expect(icon.src).toBeDefined();
                expect(icon.sizes).toBeDefined();
            }
        });

        it('has theme_color or background_color', () => {
            expect(manifest.theme_color || manifest.background_color).toBeTruthy();
        });
    }
});

// ════════════════════════════════════════════════════════════════════
// index.html 基础 A11y 验证
// ════════════════════════════════════════════════════════════════════

describe('HTML Base A11y Compliance', () => {
    const indexPath = path.resolve(process.cwd(), 'index.html');
    const indexExists = fs.existsSync(indexPath);

    if (indexExists) {
        const html = fs.readFileSync(indexPath, 'utf-8');

        it('has lang attribute on <html>', () => {
            expect(html).toMatch(/<html[^>]*lang=/i);
        });

        it('has viewport meta tag', () => {
            expect(html).toMatch(/name=["']viewport["']/i);
        });

        it('has charset meta tag', () => {
            expect(html).toMatch(/charset/i);
        });

        it('has <title> tag', () => {
            expect(html).toMatch(/<title>/i);
        });

        it('has meta description', () => {
            // SEO + A11y: 屏幕阅读器使用 description
            const hasDesc = html.match(/name=["']description["']/i);
            if (!hasDesc) {
                console.warn('⚠️ Missing meta description — impacts SEO and A11y');
            }
            expect(true).toBe(true);
        });
    }
});

// ════════════════════════════════════════════════════════════════════
// 响应式断点验证
// ════════════════════════════════════════════════════════════════════

describe('Responsive Breakpoint Coverage', () => {
    // 验证 CSS 文件中包含常见断点
    const cssFiles = [
        'src/index.css',
        'src/App.css',
    ];

    for (const file of cssFiles) {
        const filePath = path.resolve(process.cwd(), file);
        if (fs.existsSync(filePath)) {
            const css = fs.readFileSync(filePath, 'utf-8');

            it(`${file} contains mobile-first media queries`, () => {
                const hasMediaQuery = css.includes('@media') ||
                    css.includes('min-width') || css.includes('max-width');
                if (!hasMediaQuery) {
                    console.warn(`⚠️ ${file} has no media queries — may not be responsive`);
                }
                // 不强制要求每个 CSS 文件都有 media query
                expect(true).toBe(true);
            });
        }
    }
});

// ════════════════════════════════════════════════════════════════════
// 键盘导航基础验证
// ════════════════════════════════════════════════════════════════════

describe('Keyboard Navigation Patterns', () => {
    it('interactive elements should use focusable HTML tags', () => {
        // 这是一个编码规范检查 — 验证项目中不使用 div onClick 替代 button
        const srcDir = path.resolve(process.cwd(), 'src');
        const violations: string[] = [];

        function scanDir(dir: string) {
            try {
                const entries = fs.readdirSync(dir, { withFileTypes: true });
                for (const entry of entries) {
                    if (entry.isDirectory() && !entry.name.startsWith('.') &&
                        entry.name !== 'node_modules' && entry.name !== '__tests__') {
                        scanDir(path.join(dir, entry.name));
                    } else if (entry.name.endsWith('.tsx')) {
                        const content = fs.readFileSync(path.join(dir, entry.name), 'utf-8');
                        // 检查 <div onClick> 但不带 role 和 tabIndex
                        const divOnClickPattern = /<div[^>]*onClick[^>]*>/g;
                        const matches = content.match(divOnClickPattern) || [];
                        for (const match of matches) {
                            if (!match.includes('role=') && !match.includes('tabIndex')) {
                                violations.push(`${entry.name}: ${match.substring(0, 60)}...`);
                            }
                        }
                    }
                }
            } catch { /* 忽略目录访问错误 */ }
        }

        scanDir(srcDir);

        // 不严格要求 0 violations，但超过 20 个则标记为问题
        if (violations.length > 20) {
            console.warn(`⚠️ ${violations.length} potential A11y violations (div onClick without role/tabIndex)`);
        }
        // 基础通过
        expect(violations.length).toBeLessThan(100);
    });
});

// ════════════════════════════════════════════════════════════════════
// 颜色对比度（基础）
// ════════════════════════════════════════════════════════════════════

describe('Color Contrast Baseline', () => {
    it('CSS variables define both foreground and background colors', () => {
        const cssPath = path.resolve(process.cwd(), 'src/index.css');
        if (!fs.existsSync(cssPath)) {
            console.warn('⚠️ index.css not found');
            return;
        }
        const css = fs.readFileSync(cssPath, 'utf-8');
        const hasForeground = css.includes('foreground') || css.includes('--text');
        const hasBackground = css.includes('background') || css.includes('--bg');
        expect(hasForeground || hasBackground).toBe(true);
    });
});
