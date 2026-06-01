// ============================================================
//  exemple.fs  —  Exemple de programme FrançaisScript
//
//  Ce programme démontre la syntaxe du langage :
//    • variables locales et statiques
//    • boucle tantque
//    • condition si / sinon
//    • appels de fonctions
//    • retour de valeur
// ============================================================

programme Calculatrice {

    // Variable statique partagée par toutes les fonctions
    statique entier compteur;

    // ── Calcule la somme de 1 + 2 + ... + n ──────────────────
    fonction entier somme(entier n) {
        var entier total;
        var entier i;

        laisser total = 0;
        laisser i = 1;

        tantque (i < n) {
            laisser total = total + i;
            laisser i = i + 1;
        }
        laisser total = total + n;   // inclure n lui-même
        retourner total;
    }

    // ── Retourne le maximum de deux entiers ──────────────────
    fonction entier maximum(entier a, entier b) {
        si (a > b) {
            retourner a;
        } sinon {
            retourner b;
        }
    }

    // ── Calcule n! (factorielle) de manière récursive ────────
    fonction entier factorielle(entier n) {
        si (n < 2) {
            retourner 1;
        }
        retourner n * Calculatrice.factorielle(n - 1);
    }

    // ── Point d'entrée principal ──────────────────────────────
    fonction vide principale() {
        var entier s;
        var entier m;
        var entier f;

        // Somme de 1 à 10  →  55
        laisser s = Calculatrice.somme(10);

        // Maximum de 42 et 17  →  42
        laisser m = Calculatrice.maximum(42, 17);

        // 5! = 120
        laisser f = Calculatrice.factorielle(5);

        // Incrémenter le compteur statique
        laisser compteur = compteur + 1;

        // Afficher les résultats (suppose une lib d'E/S standard)
        faire Sortie.imprimerEntier(s);
        faire Sortie.imprimerEntier(m);
        faire Sortie.imprimerEntier(f);

        retourner;
    }
}