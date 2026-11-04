const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const testDashboardData = {
    stocks: {
        wb: {
            chart_data: { labels: ['Котовск', 'Самара', 'Склад WB РФ'], datasets: [{ label: 'A', data: [2, 4, 100] }] },
            chart_data_fbs: { labels: ['Москва', 'Fox КРД'], datasets: [{ label: 'A', data: [7, 5] }] },
        },
        ozon: {
            chart_data: {
                labels: ['Пушкино', 'Хоругвино', 'Шушары'],
                datasets: [{ label: 'A', data: [10, 20, 30] }],
                clusters: [
                    { name: 'Москва, МО и Дальние регионы', start_index: 0, end_index: 1 },
                    { name: 'Санкт-Петербург и СЗО', start_index: 2, end_index: 2 },
                ],
            },
            chart_data_fbs: { labels: ['Ozon own'], datasets: [{ label: 'A', data: [3] }] },
        },
    },
    period_data: {},
};
for (const key of ['today', 'yesterday', 'days_3', 'days_7', 'days_30']) {
    testDashboardData.period_data[key] = {
        wb: { consumption_by_product: [{ article: 'A', by_warehouse: [
            { name: 'Склад WB РФ', count: key === 'days_7' ? 12 : 0, source: 'fbw' },
            { name: 'Москва', count: key === 'days_7' ? 4 : 0, source: 'fbs' },
            { name: 'Fox КРД', count: key === 'days_7' ? 3 : 0, source: 'fbs' },
        ] }] },
        ozon: { sales_by_product: [{ article: 'A', by_warehouse: [
            { name: 'Пушкино', count: 2, source: 'fbo' },
            { name: 'Хоругвино', count: 3, source: 'fbo' },
            { name: 'Шушары', count: 4, source: 'fbo' },
            { name: 'Ozon own', count: 5, source: 'fbs' },
        ] }] },
    };
}

let source = fs.readFileSync('main.js', 'utf8')
    .replace('let dashboardData = null;', 'let dashboardData = globalThis.testDashboardData;');
source += '\nmodule.exports = { buildMonitoringData, getWarehouseCluster };';
const document = { getElementById: () => null, addEventListener: () => {} };
const context = {
    document, console, Intl, Chart: function () {},
    module: { exports: {} }, testDashboardData,
    setInterval: () => {}, setTimeout: () => {}, clearInterval: () => {},
    window: {}, fetch: () => Promise.reject(new Error('not used')),
    URLSearchParams, Date, Math, Number, String, Array, Object, Map, Set,
};
vm.createContext(context);
vm.runInContext(source, context);
const rows = context.module.exports.buildMonitoringData();
const get = (mp, source, cluster, warehouse) => rows.find(row =>
    row.mp === mp && row.source === source && row.cluster === cluster && row.warehouse === warehouse
);
assert.equal(get('wb', 'fbw', 'Склад WB РФ · FBW (единый пул)', 'Склад WB РФ').stock, 100);
assert.equal(get('wb', 'fbw', 'Склад WB РФ · FBW (единый пул)', 'Склад WB РФ').orders7d, 12);
assert.equal(get('wb', 'fbs', 'Мои склады', 'Москва').orders7d, 4);
assert.equal(get('wb', 'fbs', 'Мои склады', 'Fox КРД').orders7d, 3);
assert.equal(get('ozon', 'fbo', 'Москва, МО и Дальние регионы', 'Склад кластера').stock, 30);
assert.equal(get('ozon', 'fbo', 'Санкт-Петербург и СЗО', 'Склад кластера').stock, 30);
assert.equal(get('ozon', 'fbo', 'Москва, МО и Дальние регионы', 'Склад кластера').orders7d, 5);
assert.equal(get('ozon', 'fbs', 'Мои склады', 'Ozon own').orders7d, 5);
console.log('PASS: WB pooled FBW, distinct WB seller warehouses, Ozon cluster aggregation, separate Ozon FBS');
