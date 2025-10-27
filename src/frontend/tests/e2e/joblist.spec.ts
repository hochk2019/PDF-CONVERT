import { expect, test } from '@playwright/test';

const TOKEN_STORAGE_KEY = 'pdf-convert-token';

test.describe('Job list artifact downloads', () => {
  test('renders artifact download buttons and triggers browser downloads', async ({ page }) => {
    const jobId = '11111111-2222-3333-4444-555555555555';

    await page.context().addInitScript(
      ({ key, token }) => {
        window.localStorage.setItem(key, token);
      },
      { key: TOKEN_STORAGE_KEY, token: 'test-token' },
    );

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
          email: 'user@example.com',
          full_name: 'Test User',
          is_active: true,
          is_admin: false,
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.route('**/api/v1/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: jobId,
            status: 'completed',
            input_filename: 'invoice.pdf',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            result_payload: {
              artifacts: {
                docx: `/downloads/${jobId}.docx`,
                xlsx: `/downloads/${jobId}.xlsx`,
              },
            },
            error_message: null,
            llm_options: {},
          },
        ]),
      });
    });

    await page.route(`**/api/v1/jobs/${jobId}/result`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ text: 'converted' }),
      });
    });

    await page.route(`**/api/v1/jobs/${jobId}/artifacts/docx`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        body: 'docx-data',
      });
    });

    await page.route(`**/api/v1/jobs/${jobId}/artifacts/xlsx`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        body: 'xlsx-data',
      });
    });

    await page.route('**/ws/jobs/**', (route) => route.abort());

    await page.goto('/jobs');

    await expect(page.getByRole('heading', { name: 'Danh sách xử lý gần đây' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'invoice.pdf' })).toBeVisible();

    const jsonDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Tải JSON' }).click();
    const jsonDownload = await jsonDownloadPromise;
    expect(jsonDownload.suggestedFilename()).toBe(`${jobId}.json`);
    await jsonDownload.delete();

    const docxDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'DOCX' }).click();
    const docxDownload = await docxDownloadPromise;
    expect(docxDownload.suggestedFilename()).toBe(`${jobId}.docx`);
    await docxDownload.delete();

    const xlsxDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'XLSX' }).click();
    const xlsxDownload = await xlsxDownloadPromise;
    expect(xlsxDownload.suggestedFilename()).toBe(`${jobId}.xlsx`);
    await xlsxDownload.delete();
  });
});
