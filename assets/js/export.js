// 下载Excel
        function exportToExcel() {
            if (appState.orders.length === 0) {
                toast.error('没有订单可以下载');
                return;
            }

            const wb = XLSX.utils.book_new();
            const orderRows = [['导入编号', '收货人', '手机', '收货地址', '收货人信息(解析)', '应收邮资', '应收合计', '客服备注', '客户账号', '销售渠道名称', '结算方式', '物流公司', '物流单号', '支付单号', '收款账户', '业务员']];
            const prodRows = [['导入编号(关联订单)', '货品名称', '条码', '货品编号', '规格', '数量', '单价']];

            appState.orders.forEach((r, idx) => {
                const importId = r.phone || (idx + 1); // 🌟 优先使用手机号作为导入编号
                orderRows.push([
                    importId, r.receiver, r.phone, r.address,
                    `${r.receiver} ${r.phone} ${r.address}`,
                    r.freight || 0, r.total || 0, r.note || '',
                    r.account || '', r.salesChannel || '仝心科技线下批发',
                    r.payMethod || '欠款计应收', r.express || '',
                    r.trackingNumber || '', '', // 物流单号, 支付单号
                    r.receipt || '', r.salesman || ''
                ]);
                (r.products || []).forEach(p => {
                    prodRows.push([
                        importId,
                        p.matchedName || p.searchName,
                        p.productInfo?.['条码'] || p.productInfo?.['货品条码'] || p.barcode || '',
                        p.productInfo?.['货品编号'] || p.item_no || '',
                        p.productInfo?.['规格'] || p.spec || '',
                        p.qty, p.price
                    ]);
                });
            });

            XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(orderRows), '订单');
            XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(prodRows), '货品');
            const dataStr = new Date().toLocaleDateString().replace(/\//g, '_');
            XLSX.writeFile(wb, `订单分表_${dataStr}_共${appState.orders.length}单.xlsx`);

            toast.success('订单已下载为Excel文件');
        }

        // 清空所有订单
        function clearAllOrders() {
            showConfirmDialog(
                '确认清空所有订单？',
                '此操作将删除所有已识别的订单，且无法撤销。请确保已下载重要数据。',
                () => {
                    appState.orders = [];
                    renderKeepScroll();
                    toast.success('已清空所有订单');
                }
            );
        }
