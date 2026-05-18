/* ====== Store/Shopping Module ====== */

const PRODUCTS_ENDPOINT = '/api/products/';
const PRODUCT_STATS_ENDPOINT = '/api/products/stats';
const CART_ENDPOINT = '/api/cart';

class ShoppingCart {
    constructor() {
        this.items = Storage.get('cart') || [];
        this.products = [];
        this.productSignature = '';
        this.cartSignature = this.buildCartSignature(this.items);
        this.cartInFlight = false;
        this.cartRefreshInterval = null;
        this.currentFilter = 'all';
        this.currentSort = 'recent';
        this.currentSearch = '';
        this.init();
    }

    async init() {
        await this.loadProducts();
        await this.loadCartFromServer(true);
        this.updateCategoryCounts();
        this.renderProducts();
        this.updateCartUI();
        this.refreshInventoryLoop();
        this.startCartRefreshLoop();
        this.attachCartSyncListeners();
    }

    async loadProducts() {
        try {
            const response = await fetch(PRODUCTS_ENDPOINT, { cache: 'no-store' });
            const data = await response.json();
            this.products = Array.isArray(data) ? data : (data.products || []);
            this.productSignature = this.buildProductSignature();
            this.updateInventorySummary();
            this.refreshSummaryFromStats();
        } catch (error) {
            console.error('Failed to load products:', error);
            toast.error('Failed to load products');
        }
    }

    buildProductSignature() {
        return this.products
            .map(product => `${product.id}:${product.stock}:${product.price}`)
            .join('|');
    }

    refreshInventoryLoop() {
        setInterval(async () => {
            try {
                // Keep top-level catalog counters fresh even when the full list doesn't change.
                this.refreshSummaryFromStats();

                const response = await fetch(PRODUCTS_ENDPOINT, { cache: 'no-store' });
                const data = await response.json();
                const nextProducts = Array.isArray(data) ? data : (data.products || []);
                const nextSignature = nextProducts
                    .map(product => `${product.id}:${product.stock}:${product.price}`)
                    .join('|');

                if (nextSignature !== this.productSignature) {
                    this.products = nextProducts;
                    this.productSignature = nextSignature;
                    this.updateCategoryCounts();
                    this.renderProducts();
                    this.updateInventorySummary();
                }
            } catch (error) {
                console.error('Failed to refresh inventory:', error);
            }
        }, 5000);
    }

    async refreshSummaryFromStats() {
        try {
            const response = await fetch(PRODUCT_STATS_ENDPOINT, { cache: 'no-store' });
            const stats = await response.json();
            this.updateInventorySummary(stats);
        } catch (error) {
            // Fallback to local product list summary if stats endpoint fails.
            this.updateInventorySummary();
        }
    }

    addToCart(productId) {
        const product = this.products.find(p => p.id === productId);
        if (!product) {
            toast.error('Product not found');
            return;
        }

        this.postCartForm(`${CART_ENDPOINT}/add`, { product_id: productId })
            .then(async () => {
                await this.loadCartFromServer(true);
                toast.success(`${product.name} added to cart`);
            })
            .catch((error) => {
                console.error('Failed to add item to cart:', error);
                toast.error('Failed to update cart');
            });
    }

    removeFromCart(productId) {
        const item = this.items.find(entry => entry.id === productId);
        if (!item) return;

        this.postCartForm(`${CART_ENDPOINT}/update`, {
            item_name: item.name,
            quantity: 0,
        })
            .then(async () => {
                await this.loadCartFromServer(true);
                toast.success('Item removed from cart');
            })
            .catch((error) => {
                console.error('Failed to remove item from cart:', error);
                toast.error('Failed to update cart');
            });
    }

    updateQuantity(productId, change) {
        const item = this.items.find(item => item.id === productId);
        if (!item) return;

        const nextQuantity = item.quantity + change;
        const payload = {
            item_name: item.name,
            quantity: Math.max(nextQuantity, 0),
        };

        this.postCartForm(`${CART_ENDPOINT}/update`, payload)
            .then(async () => {
                await this.loadCartFromServer(true);
            })
            .catch((error) => {
                console.error('Failed to update cart quantity:', error);
                toast.error('Failed to update quantity');
            });
    }

    clearCart() {
        if (confirm('Are you sure you want to clear your cart?')) {
            this.postCartForm(`${CART_ENDPOINT}/clear`)
                .then(async () => {
                    await this.loadCartFromServer(true);
                    toast.success('Cart cleared');
                })
                .catch((error) => {
                    console.error('Failed to clear cart:', error);
                    toast.error('Failed to clear cart');
                });
        }
    }

    saveCart() {
        Storage.set('cart', this.items);
        localStorage.setItem('cart:updated-at', String(Date.now()));
    }

    buildCartSignature(items) {
        return (items || [])
            .map(item => `${item.id}:${item.quantity}:${item.price}`)
            .join('|');
    }

    normalizeServerCartItems(serverCart = {}) {
        const rawItems = Array.isArray(serverCart.items) ? serverCart.items : [];
        return rawItems.map((item) => {
            const matchedProduct = this.products.find(product => product.id === item.product_id);
            return {
                id: item.product_id,
                name: item.name,
                price: Number(item.price || 0),
                image: matchedProduct?.image || '/static/images/placeholder.png',
                weight: Number(item.weight || 0),
                quantity: Number(item.qty || 0),
            };
        });
    }

    async loadCartFromServer(force = false) {
        if (this.cartInFlight) return;
        this.cartInFlight = true;

        try {
            const response = await fetch(CART_ENDPOINT, { cache: 'no-store' });
            const serverCart = await response.json();
            const nextItems = this.normalizeServerCartItems(serverCart);
            const nextSignature = this.buildCartSignature(nextItems);

            if (!force && nextSignature === this.cartSignature) return;

            this.items = nextItems;
            this.cartSignature = nextSignature;
            this.saveCart();
            this.updateCartUI();
        } catch (error) {
            console.error('Failed to refresh cart:', error);
        } finally {
            this.cartInFlight = false;
        }
    }

    async postCartForm(url, payload = {}) {
        const body = new URLSearchParams();
        Object.entries(payload).forEach(([key, value]) => {
            body.append(key, String(value));
        });

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            },
            body: body.toString(),
        });

        if (!response.ok) {
            throw new Error(`Request failed with ${response.status}`);
        }

        return response.json().catch(() => ({}));
    }

    startCartRefreshLoop() {
        if (this.cartRefreshInterval) {
            clearInterval(this.cartRefreshInterval);
        }

        this.cartRefreshInterval = setInterval(() => {
            this.loadCartFromServer();
        }, 3000);
    }

    attachCartSyncListeners() {
        window.addEventListener('focus', () => this.loadCartFromServer(true));

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                this.loadCartFromServer(true);
            }
        });

        window.addEventListener('pageshow', () => this.loadCartFromServer(true));

        window.addEventListener('storage', (event) => {
            if (event.key === 'cart:updated-at') {
                this.loadCartFromServer(true);
            }
        });
    }

    getTotalPrice() {
        return this.items.reduce((total, item) => total + item.price * item.quantity, 0);
    }

    getTotalItems() {
        return this.items.reduce((total, item) => total + item.quantity, 0);
    }

    getTotalWeight() {
        return this.items.reduce((total, item) => total + item.weight * item.quantity, 0);
    }

    renderProducts() {
        const grid = document.getElementById('products-grid');
        const emptyState = document.getElementById('empty-state');
        
        if (!grid) return;

        let filtered = [...this.products];

        if (this.currentSearch) {
            const lowerQuery = this.currentSearch.toLowerCase();
            filtered = filtered.filter(product => 
                product.name.toLowerCase().includes(lowerQuery) ||
                product.category.toLowerCase().includes(lowerQuery)
            );
        }

        // Filter by category
        if (this.currentFilter !== 'all') {
            filtered = filtered.filter(p => p.category.toLowerCase() === this.currentFilter);
        }

        // Sort
        if (this.currentSort === 'price-low') {
            filtered.sort((a, b) => a.price - b.price);
        } else if (this.currentSort === 'price-high') {
            filtered.sort((a, b) => b.price - a.price);
        } else if (this.currentSort === 'popular') {
            filtered.sort((a, b) => (b.rating || 0) - (a.rating || 0));
        }

        if (filtered.length === 0) {
            grid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');

        if (this.currentFilter === 'all' && !this.currentSearch) {
            grid.innerHTML = this.renderCategoryGroups(filtered);
            return;
        }

        grid.innerHTML = filtered.map(product => this.createProductCard(product)).join('');
    }

    updateCategoryCounts() {
        const counts = this.products.reduce((accumulator, product) => {
            const key = (product.category || 'other').toLowerCase();
            accumulator[key] = (accumulator[key] || 0) + 1;
            accumulator.all += 1;
            return accumulator;
        }, { all: 0 });

        document.querySelectorAll('.category-count').forEach(element => {
            const category = element.dataset.countFor;
            element.textContent = counts[category] || 0;
        });
    }

    renderCategoryGroups(products) {
        const grouped = products.reduce((accumulator, product) => {
            const key = (product.category || 'Other').trim();
            if (!accumulator[key]) {
                accumulator[key] = [];
            }
            accumulator[key].push(product);
            return accumulator;
        }, {});

        const categoryOrder = ['Snacks', 'Drinks', 'Books', 'Electronics', 'Household', 'Stationery', 'Fresh'];
        const sortedCategories = Object.keys(grouped).sort((left, right) => {
            const leftIndex = categoryOrder.indexOf(left);
            const rightIndex = categoryOrder.indexOf(right);

            if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
            if (leftIndex === -1) return 1;
            if (rightIndex === -1) return -1;
            return leftIndex - rightIndex;
        });

        return sortedCategories.map(category => {
            const items = grouped[category];
            return `
                <section class="col-span-full mb-4">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <h3 class="text-2xl font-black text-slate-900">${category}</h3>
                            <p class="text-sm text-slate-500">${items.length} products available</p>
                        </div>
                        <span class="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                            Category view
                        </span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                        ${items.map(product => this.createProductCard(product)).join('')}
                    </div>
                </section>
            `;
        }).join('');
    }

    createProductCard(product) {
        const stock = Number(product.stock || 0);
        const inStock = stock > 0;
        return `
            <div class="card cursor-pointer group">
                <div class="relative h-48 bg-gradient-to-br from-slate-100 to-slate-200 rounded-lg overflow-hidden mb-4 flex items-center justify-center">
                    <img src="${product.image || '/static/images/placeholder.png'}" 
                         alt="${product.name}" 
                         class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                    />
                    <div class="absolute bottom-3 left-3">
                        <span class="${inStock ? 'bg-green-500/90' : 'bg-gray-500/90'} text-white text-xs px-2 py-1 rounded-full font-medium">
                            ${inStock ? `In Stock (${stock})` : 'Out of Stock'}
                        </span>
                    </div>
                    ${product.discount ? `
                        <div class="absolute top-3 right-3 bg-red-500 text-white px-3 py-1 rounded-full text-xs font-bold">
                            -${product.discount}%
                        </div>
                    ` : ''}
                </div>
                
                <p class="text-xs text-slate-500 mb-1 uppercase tracking-wide">${product.category}</p>
                <h3 class="font-bold text-slate-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition">${product.name}</h3>
                
                <div class="flex items-center gap-2 mb-3">
                    <span class="text-lg font-black text-slate-900">₹${product.price.toFixed(2)}</span>
                    ${product.original_price ? `
                        <span class="text-sm text-slate-500 line-through">₹${product.original_price.toFixed(2)}</span>
                    ` : ''}
                </div>
                
                <p class="text-xs text-slate-600 mb-4">
                    <i class="fas fa-balance-scale mr-1"></i>${product.weight}g
                </p>
                
                <button onclick="cart.addToCart(${product.id})" 
                        class="w-full btn btn-primary justify-center ${!inStock ? 'opacity-50 cursor-not-allowed' : ''}"
                        ${!inStock ? 'disabled' : ''}>
                    <i class="fas fa-plus"></i> Add to Cart
                </button>
            </div>
        `;
    }

    updateCartUI() {
        const totalItems = this.getTotalItems();

        // Keep all cart badges in sync across page layouts.
        const badgeIds = ['cart-badge-float', 'floating-cart-badge', 'navbar-cart-badge', 'cart-count'];
        badgeIds.forEach((badgeId) => {
            const badge = document.getElementById(badgeId);
            if (badge) badge.textContent = totalItems;
        });

        window.dispatchEvent(new CustomEvent('cart:changed', {
            detail: { count: totalItems },
        }));

        this.renderCartItems();
        this.updateCartSummary();
    }

    updateInventorySummary(stats = null) {
        const totalProductsEl = document.getElementById('product-count');
        const heroTotalProductsEl = document.getElementById('hero-product-count');
        const inStockEl = document.getElementById('in-stock');
        const heroInStockEl = document.getElementById('hero-in-stock');
        const inStockRateEl = document.getElementById('in-stock-rate');
        const outOfStockEl = document.getElementById('out-of-stock');
        const inStockMeterEl = document.getElementById('in-stock-meter');
        const productFootnoteEl = document.getElementById('product-footnote');

        const totalProducts = stats && typeof stats.totalProducts === 'number'
            ? stats.totalProducts
            : this.products.length;
        const inStockCount = stats && typeof stats.inStock === 'number'
            ? stats.inStock
            : this.products.filter(product => Number(product.stock || 0) > 0).length;
        const outOfStockCount = Math.max(totalProducts - inStockCount, 0);
        const inStockRate = totalProducts > 0
            ? Math.round((inStockCount / totalProducts) * 100)
            : 0;

        if (totalProductsEl) totalProductsEl.textContent = totalProducts;
        if (heroTotalProductsEl) heroTotalProductsEl.textContent = totalProducts;
        if (inStockEl) {
            inStockEl.textContent = inStockCount;
            if (heroInStockEl) heroInStockEl.textContent = inStockCount;
        }
        if (inStockRateEl) inStockRateEl.textContent = `${inStockRate}% available`;
        if (outOfStockEl) outOfStockEl.textContent = `${outOfStockCount} out`;
        if (inStockMeterEl) inStockMeterEl.style.width = `${inStockRate}%`;
        if (productFootnoteEl) {
            productFootnoteEl.textContent = totalProducts > 0
                ? `${outOfStockCount} out of stock`
                : 'Catalog items';
        }
    }

    renderCartItems() {
        const container = document.getElementById('cart-items-container');
        const emptyMsg = document.getElementById('cart-empty');
        
        if (!container) return;

        if (this.items.length === 0) {
            container.innerHTML = '';
            emptyMsg.classList.remove('hidden');
            return;
        }

        emptyMsg.classList.add('hidden');
        container.innerHTML = this.items.map(item => `
            <div class="group relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50/80 p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3 flex-1 min-w-0">
                    <img src="${item.image}" alt="${item.name}" class="w-12 h-12 rounded-xl object-cover ring-1 ring-slate-200" />
                    <div>
                        <p class="font-semibold text-sm text-slate-900 truncate">${item.name}</p>
                        <p class="text-xs text-slate-500">₹${item.price.toFixed(2)} each</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1">
                    <button onclick="cart.updateQuantity(${item.id}, -1)" class="h-7 w-7 rounded-lg text-slate-600 hover:bg-slate-100">
                        <i class="fas fa-minus text-xs"></i>
                    </button>
                    <span class="w-6 text-center font-bold">${item.quantity}</span>
                    <button onclick="cart.updateQuantity(${item.id}, 1)" class="h-7 w-7 rounded-lg text-slate-600 hover:bg-slate-100">
                        <i class="fas fa-plus text-xs"></i>
                    </button>
                </div>
                
                <button onclick="cart.removeFromCart(${item.id})" class="ml-2 h-9 w-9 rounded-xl text-red-500 hover:bg-red-50 hover:text-red-700">
                    <i class="fas fa-trash text-sm"></i>
                </button>
                </div>
                <div class="mt-3 flex items-center justify-between text-xs">
                    <span class="font-semibold uppercase tracking-wide text-slate-400">Line Total</span>
                    <span class="text-sm font-black text-slate-900">₹${(item.price * item.quantity).toFixed(2)}</span>
                </div>
            </div>
        `).join('');
    }

    updateCartSummary() {
        const summary = document.getElementById('cart-summary');
        const subtotal = this.getTotalPrice();
        const tax = subtotal * 0.05;
        const total = subtotal + tax;

        if (summary) {
            summary.classList.toggle('hidden', this.items.length === 0);
            
            const subtotalEl = summary.querySelector('#subtotal');
            const discountEl = summary.querySelector('#discount');
            const totalEl = summary.querySelector('#total');
            
            if (subtotalEl) subtotalEl.textContent = formatCurrency(subtotal);
            if (discountEl) discountEl.textContent = `-${formatCurrency(0)}`;
            if (totalEl) totalEl.textContent = formatCurrency(total);
        }
    }

    filterByCategory(category) {
        this.currentFilter = category;
        this.renderProducts();
    }

    sortBy(sortType) {
        this.currentSort = sortType;
        this.renderProducts();
    }

    searchProducts(query) {
        this.currentSearch = query.trim();
        this.renderProducts();
    }
}

// Initialize cart
let cart;
document.addEventListener('DOMContentLoaded', () => {
    cart = new ShoppingCart();
});

/* ====== Event Handlers ====== */

function scrollToProducts() {
    const section = document.getElementById('products-section');
    if (section) section.scrollIntoView({ behavior: 'smooth' });
}

function toggleCart() {
    const sidebar = document.getElementById('cart-sidebar');
    const overlay = document.getElementById('cart-overlay');
    
    if (sidebar && overlay) {
        const isClosed = sidebar.classList.contains('translate-x-full');
        sidebar.classList.toggle('translate-x-full');
        overlay.classList.toggle('opacity-0');
        overlay.classList.toggle('invisible');
        document.body.classList.toggle('overflow-hidden', isClosed);
    }
}

function goToCheckout() {
    window.location.href = '/payment';
}

function toggleStoreControls() {
    const panel = document.getElementById('store-controls-panel');
    const toggle = document.getElementById('store-controls-toggle');
    if (!panel || !toggle) return;

    panel.classList.toggle('hidden');
    const expanded = !panel.classList.contains('hidden');
    toggle.setAttribute('aria-expanded', String(expanded));
}

function toggleCategoryFilters() {
    const panel = document.getElementById('category-filters-panel');
    const toggle = document.getElementById('category-filters-toggle');
    if (!panel || !toggle) return;

    panel.classList.toggle('hidden');
    const expanded = !panel.classList.contains('hidden');
    toggle.setAttribute('aria-expanded', String(expanded));
}

function filterCategory(category) {
    if (cart) {
        cart.filterByCategory(category);
        
        // Update button styles
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.toggle('bg-blue-600', btn.dataset.category === category);
            btn.classList.toggle('text-white', btn.dataset.category === category);
            btn.classList.toggle('bg-slate-100', btn.dataset.category !== category);
            btn.classList.toggle('text-slate-700', btn.dataset.category !== category);
        });

        const categoryPanel = document.getElementById('category-filters-panel');
        const categoryToggle = document.getElementById('category-filters-toggle');
        if (window.innerWidth < 768 && categoryPanel && categoryToggle) {
            categoryPanel.classList.add('hidden');
            categoryToggle.setAttribute('aria-expanded', 'false');
        }
    }
}

function handleSort(sortType) {
    if (cart) cart.sortBy(sortType);
}

function handleSearch(event) {
    event.preventDefault();
    const input = document.getElementById('search-input');
    if (input && cart) {
        cart.searchProducts(input.value);
    }
}

// Debounced search for real-time filtering
const debouncedSearch = debounce((query) => {
    if (cart) cart.searchProducts(query);
}, 300);

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            debouncedSearch(e.target.value);
        });
    }

    const storeControlsPanel = document.getElementById('store-controls-panel');
    const storeControlsToggle = document.getElementById('store-controls-toggle');
    const categoryPanel = document.getElementById('category-filters-panel');
    const categoryToggle = document.getElementById('category-filters-toggle');

    if (window.innerWidth >= 768) {
        if (storeControlsPanel) storeControlsPanel.classList.remove('hidden');
        if (categoryPanel) categoryPanel.classList.remove('hidden');
    }

    window.addEventListener('resize', () => {
        if (window.innerWidth >= 768) {
            if (storeControlsPanel) storeControlsPanel.classList.remove('hidden');
            if (categoryPanel) categoryPanel.classList.remove('hidden');
            if (storeControlsToggle) storeControlsToggle.setAttribute('aria-expanded', 'false');
            if (categoryToggle) categoryToggle.setAttribute('aria-expanded', 'false');
        }
    });
});
