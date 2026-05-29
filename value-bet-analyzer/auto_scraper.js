/**
 * Robust Headless Auto-Scraper
 * Searches for team stats and scrapes them in background
 * Supports: FBref (Primary), FlashScore (Fallback)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');

// Setup paths
const BETTING_BOT_DIR = path.join(os.homedir(), 'Documents', 'BettingBot');
const CSV_FILE = path.join(BETTING_BOT_DIR, 'team_stats.csv');

if (!fs.existsSync(BETTING_BOT_DIR)) fs.mkdirSync(BETTING_BOT_DIR, { recursive: true });

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise(r => rl.question(q, r));

async function scrapeFlashScore(page, teamName) {
    console.log(`⚠️ FBref failed/skipped. Trying FlashScore for "${teamName}"...`);

    try {
        await page.goto(`https://www.google.com/search?q=${encodeURIComponent(teamName + ' flashscore')}`);
        const link = page.locator('a[href*="flashscore.com/team/"]').first();

        if (await link.count() === 0) {
            console.log('❌ Could not find FlashScore page on Google.');
            return false;
        }

        const url = await link.getAttribute('href');
        console.log(`Found FlashScore page: ${url}`);

        await page.goto(url);
        await page.waitForLoadState('networkidle'); // FlashScore needs more time

        const title = await page.title();
        const detectedName = await page.locator('.heading__name').textContent().catch(() => title.split('|')[0].trim());
        console.log(`✅ Loaded: ${detectedName}`);

        // FlashScore specific scraping
        // Note: FlashScore layout is complex. This is a best-effort scraper.
        // Looking for form icons in the last 5 matches
        const matches = await page.locator('.formIcon').all(); // Common class for W/D/L icons
        const form = [];

        // If .formIcon doesn't work, try .wld--w, .wld--d, .wld--l generic classes
        if (matches.length === 0) {
            console.log('⚠️ Could not find simple form icons, standard FlashScore structure might have changed.');
            return false;
        }

        for (let i = 0; i < Math.min(5, matches.length); i++) {
            const text = await matches[i].textContent();
            if (text.includes('W')) form.push('W');
            else if (text.includes('D')) form.push('D');
            else if (text.includes('L')) form.push('L');
        }

        if (form.length === 0) return false;

        // Goals are harder on FlashScore overview, setting to 0/0 for now if safe
        // Or we can try to find the "Results" tab
        // For simplicity, we'll save the FORM which is the most important part
        const goalsScored = 0;
        const goalsConceded = 0;

        const csvLine = `${detectedName},${form.join(',')},${goalsScored},${goalsConceded},0,Unknown,Home\n`;
        fs.appendFileSync(CSV_FILE, csvLine);

        console.log(`✅ Saved ${detectedName} (from FlashScore)!`);
        console.log(`   Form: [${form.join(',')}]`);
        console.log(`   Saved to: ${CSV_FILE}`);
        return true;

    } catch (e) {
        console.error('❌ FlashScore Error:', e.message);
        return false;
    }
}

async function scrapeTeam(teamName) {
    console.log(`\n🔍 Searching for "${teamName}" stats...`);

    // Launch headless browser
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    });
    const page = await context.newPage();

    try {
        // 1. Try FBref first (Best data)
        await page.goto(`https://www.google.com/search?q=${encodeURIComponent(teamName + ' fbref stats')}`);
        const link = page.locator('a[href*="fbref.com/en/squads"]').first();

        let fbrefSuccess = false;
        if (await link.count() > 0) {
            const url = await link.getAttribute('href');
            console.log(`Found FBref page: ${url}`);
            await page.goto(url);
            await page.waitForLoadState('domcontentloaded');

            // ... existing FBref parsing ...
            const title = await page.title();
            const detectedName = title.split('Stats')[0].trim();
            const rows = await page.locator('table.stats_table tbody tr').all();
            const form = [];
            let goalsScored = 0; let goalsConceded = 0;

            let count = 0;
            for (const row of rows) {
                if (count >= 5) break;
                const resultCell = row.locator('td[data-stat="result"]');
                if (await resultCell.count() === 0) continue;
                const result = await resultCell.textContent();
                if (!result) continue;

                const gf = await row.locator('td[data-stat="goals_for"]').textContent();
                const ga = await row.locator('td[data-stat="goals_against"]').textContent();

                if (result.includes('W')) form.push('W');
                else if (result.includes('D')) form.push('D');
                else if (result.includes('L')) form.push('L');

                goalsScored += parseInt(gf) || 0;
                goalsConceded += parseInt(ga) || 0;
                count++;
            }

            if (form.length > 0) {
                const csvLine = `${detectedName},${form.join(',')},${goalsScored},${goalsConceded},0,Unknown,Home\n`;
                fs.appendFileSync(CSV_FILE, csvLine);
                console.log(`✅ Saved ${detectedName} (from FBref)!`);
                console.log(`   Form: [${form.join(',')}]`);
                fbrefSuccess = true;
            }
        }

        if (fbrefSuccess) return true;

        // 2. If FBref failed, try FlashScore
        return await scrapeFlashScore(page, teamName);

    } catch (e) {
        console.error('❌ Error:', e.message);
        return false;
    } finally {
        await browser.close();
    }
}

async function main() {
    console.log('\n╔══════════════════════════════════════════╗');
    console.log('║   Auto-Scraper (Headless Mode)           ║');
    console.log('║   Sources: FBref -> FlashScore (Fallback)║');
    console.log('╚══════════════════════════════════════════╝\n');

    while (true) {
        const team = await ask('\nEnter team name (or "exit"): ');
        if (team.toLowerCase() === 'exit') break;
        if (!team) continue;

        await scrapeTeam(team);
    }
    rl.close();
}

main();
