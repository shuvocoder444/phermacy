with open('templates/pos/partials/search_results.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_click = '''        @click="addDrugBatch('{{ drug.fefo_batch.id }}'); searchOpen = false;"
        @keydown.enter.prevent="addDrugBatch('{{ drug.fefo_batch.id }}'); searchOpen = false;"'''

new_click = '''        {% if drug.fefo_batch %}
        @click="addDrugBatch('{{ drug.fefo_batch.id }}'); searchOpen = false;"
        @keydown.enter.prevent="addDrugBatch('{{ drug.fefo_batch.id }}'); searchOpen = false;"
        {% else %}
        @click="alert('{{ drug.brand_name|escapejs }} এর কোনো স্টক নেই। স্টক ইন করুন।'); $dispatch('open-stock-in'); searchOpen = false;"
        @keydown.enter.prevent="alert('{{ drug.brand_name|escapejs }} এর কোনো স্টক নেই। স্টক ইন করুন।'); $dispatch('open-stock-in'); searchOpen = false;"
        {% endif %}'''

norm_c = c.replace('\r\n', '\n')
norm_old = old_click.replace('\r\n', '\n')
norm_new = new_click.replace('\r\n', '\n')

assert norm_old in norm_c, 'old_click not found'
norm_c = norm_c.replace(norm_old, norm_new, 1)

with open('templates/pos/partials/search_results.html', 'w', encoding='utf-8') as f:
    f.write(norm_c)

print('search_results.html updated!')

