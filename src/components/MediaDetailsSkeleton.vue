<template>
    <div class="max-w-6xl mx-auto mt-5 p-5 animate-pulse">
        <div class="flex flex-col md:flex-row-reverse gap-6 mb-8">
            <div class="w-[300px] h-[300px] bg-gray-200 dark:bg-gray-700 rounded-xl"></div>

            <div class="flex-1 space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div v-for="i in 8" :key="i" class="h-10 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
                </div>
                <div class="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg w-full"></div>
            </div>
        </div>

        <div class="space-y-4">
            <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded w-48"></div>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div v-for="i in 6" :key="i" class="h-16 bg-gray-200 dark:bg-gray-700 rounded-xl"></div>
            </div>
        </div>
    </div>
</template>