with open('templates/pos/pos.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                    <!-- Quick Filter Input inside side panel -->
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input 
                            type="text" 
                            id="drug-search-input"
                            x-ref="searchInput"
                            x-model="quickSearch"
                            placeholder="তালিকায় নাম দিয়ে ফিল্টার করুন... (F2)" 
                            class="w-full bg-slate-50 border border-slate-200 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 font-medium focus:bg-white focus:border-emerald-500 focus:outline-none transition-all">
                    </div>'''

new_block = '''                    <!-- Instant Live Catalog Search (F2) -->
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input 
                            type="text" 
                            id="drug-search-input"
                            x-ref="searchInput"
                            x-model="quickSearch"
                            name="q"
                            placeholder="ঔষধ সার্চ করুন (যেমন: Stosec, Napa, Sergel)... (F2)" 
                            hx-get="{% url 'pos:search' %}"
                            hx-trigger="input changed delay:120ms, keyup changed delay:120ms, search"
                            hx-target="#search-results-dropdown"
                            @input="searchOpen = ($el.value.trim().length > 0)"
                            @focus="searchOpen = ($el.value.trim().length > 0)"
                            @keydown.escape="searchOpen = false"
                            class="w-full bg-white border-2 border-emerald-400/80 focus:border-emerald-600 rounded-xl pl-8 pr-14 py-2 text-xs text-slate-900 placeholder-slate-400 font-semibold focus:bg-white focus:outline-none transition-all shadow-sm">
                        
                        <div class="absolute inset-y-0 right-0 pr-2 flex items-center space-x-1">
                            <button 
                                type="button" 
                                x-show="quickSearch && quickSearch.length > 0" 
                                @click="quickSearch = ''; searchOpen = false; $refs.searchInput.value = '';" 
                                class="text-slate-400 hover:text-slate-600 text-xs px-1 font-bold">
                                ✕
                            </button>
                            <span class="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono text-emerald-800 font-bold">F2</span>
                        </div>

                        <!-- Floating Live Search Results Dropdown -->
                        <div 
                            id="search-results-dropdown" 
                            x-show="searchOpen && $refs.searchInput && $refs.searchInput.value.trim().length > 0" 
                            x-cloak
                            @click.outside="searchOpen = false"
                            class="absolute top-full left-0 right-0 mt-1 bg-white border-2 border-emerald-500 rounded-2xl shadow-2xl max-h-[72vh] overflow-y-auto z-50 divide-y divide-slate-100">
                        </div>
                    </div>'''

norm_c = content.replace('\r\n', '\n')
norm_old = old_block.replace('\r\n', '\n')
norm_new = new_block.replace('\r\n', '\n')

assert norm_old in norm_c, "old_block not found in pos.html"
norm_c = norm_c.replace(norm_old, norm_new, 1)

with open('templates/pos/pos.html', 'w', encoding='utf-8') as f:
    f.write(norm_c)

print("pos.html updated with live search bar and dropdown!")

