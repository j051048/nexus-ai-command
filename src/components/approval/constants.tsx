import React from 'react';
import { Plane, ShoppingCart, Receipt, Calendar } from 'lucide-react';

export const approvalTypes = [
    {
        id: 'travel',
        name: '出差申请',
        icon: <Plane className="w-5 h-5" />,
        example: '下周去上海出差见客户，预算2500，包括高铁和酒店',
        threshold: 3000
    },
    {
        id: 'purchase',
        name: '采购申请',
        icon: <ShoppingCart className="w-5 h-5" />,
        example: '采购一台示波器，型号DSO1104，预算8000元',
        threshold: 5000
    },
    {
        id: 'expense',
        name: '费用报销',
        icon: <Receipt className="w-5 h-5" />,
        example: '报销上周客户拜访餐费320元，附发票',
        threshold: 500
    },
    {
        id: 'leave',
        name: '请假申请',
        icon: <Calendar className="w-5 h-5" />,
        example: '申请下周一年假一天，处理私事',
        threshold: 3
    },
];
