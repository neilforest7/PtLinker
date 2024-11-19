export class BatchProcessor {
    private batch: any[] = [];
    
    constructor(private batchSize: number) {}
    
    async add(item: any, processFn: (batch: any[]) => Promise<void>) {
        this.batch.push(item);
        
        if (this.batch.length >= this.batchSize) {
            const currentBatch = [...this.batch];
            this.batch = [];
            await processFn(currentBatch);
        }
    }
    
    async flush(processFn: (batch: any[]) => Promise<void>) {
        if (this.batch.length > 0) {
            const currentBatch = [...this.batch];
            this.batch = [];
            await processFn(currentBatch);
        }
    }
} 