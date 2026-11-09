(function () {
    'use strict';

    function siap(fn) {
        if (document.readyState !== 'loading') {
            fn();
        } else {
            document.addEventListener('DOMContentLoaded', fn);
        }
    }

    /* 1. Pindahkan panel user ke dasar sidebar */
    function pindahPanelUser() {
        var sidebar = document.querySelector('.main-sidebar');
        var panel = document.querySelector('.main-sidebar .user-panel');
        if (!sidebar || !panel) { return; }
        panel.classList.add('user-panel-bawah');
        sidebar.appendChild(panel);
    }

    /* 2. Tombol "Kembali ke daftar" di halaman tambah dan ubah */
    function tambahTombolKembali() {
        if (document.querySelector('.tombol-kembali')) { return; }

        // /admin/app/model/add/  atau  /admin/app/model/<id>/change/
        var cocok = window.location.pathname.match(/^(.*\/)(add|[^\/]+\/change)\/?$/);
        if (!cocok) { return; }

        var tujuan = cocok[1];   // alamat daftar, misalnya /admin/auth/group/

        // bawa kembali filter, pencarian, dan nomor halaman daftar
        var filter = new URLSearchParams(window.location.search).get('_changelist_filters');
        if (filter) { tujuan += '?' + filter; }

        var tombol = document.createElement('a');
        tombol.href = tujuan;
        tombol.className = 'btn btn-primary btn-sm tombol-kembali';
        tombol.innerHTML = '<i class="fas fa-arrow-left mr-1"></i> Kembali ke daftar';

        var bar = document.createElement('div');
        bar.className = 'bar-kembali';
        bar.appendChild(tombol);

        var utama = document.querySelector('#content-main');
        if (utama && utama.parentNode) {
            utama.parentNode.insertBefore(bar, utama);
            return;
        }
        var wadah = document.querySelector('.content .container-fluid') ||
                    document.querySelector('.content');
        if (wadah) { wadah.insertBefore(bar, wadah.firstChild); }
    }

    /* 3. Halaman login admin: logo dipindah ke bagian atas kartu */
    function logoLogin() {
        var kotak = document.querySelector('.login-box');
        if (!kotak) { return; }

        document.body.classList.add('login-admin');

        var kartu = kotak.querySelector('.card');
        var gambar = kotak.querySelector('.login-logo img, .brand-image, img');
        if (!kartu || !gambar || gambar.closest('.login-brand')) { return; }

        var bar = document.createElement('div');
        bar.className = 'login-brand';
        bar.appendChild(gambar);
        kartu.insertBefore(bar, kartu.firstChild);

        // sisa wadah logo yang sudah kosong disembunyikan
        var lama = kotak.querySelector('.login-logo');
        if (lama && !lama.contains(kartu) && !lama.querySelector('img')) {
            lama.style.display = 'none';
        }
    }

    siap(function () {
        pindahPanelUser();
        tambahTombolKembali();
        logoLogin();
    });
})();